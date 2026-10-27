// Water treatment toy example: an OpenNN surrogate of WaterTAP's steady-state BSM2 plant
// (activated sludge + anaerobic digestion), and response optimization on that surrogate.
//
//   bsm2_surrogate train    <root> [dataset]   trains on <root>/data/bsm2_dataset.csv (or the
//                                              named file in <root>/data), writes <root>/model/
//   bsm2_surrogate optimize <root>   runs the scenarios on the saved network, writes <root>/results/
//   bsm2_surrogate predict  <root> <inputs.csv> <outputs.csv>   evaluates the saved network
//   bsm2_surrogate export   <root>   writes the trained parameters to <root>/model/parameters.json
//   bsm2_surrogate sweep    <root>   optimal set-points over an influent grid, for the dashboard
//   bsm2_surrogate validation <root> [dataset]   the validation split's targets and predictions
//
// Inputs:  do3, do4, do5 (DO set-points, mg/L), recycle (internal recycle fraction),
//          wastage (wasted fraction of the clarifier underflow), influent (m3/d), and rain (m3/d)
//          when the dataset has that column (to_show's storm network); the columns of
//          <root>/data/bsm2_dataset.csv before the outputs are the inputs
// Outputs: lcow ($/m3), sec (kWh/m3), effluent tss, cod, tn, bod5, nh4 (mg/L), biogas (m3/d)
//
// The scenarios are mirrored in verify_optima.py, which checks every answer against WaterTAP.

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>

#include "opennn/core/random_utilities.h"
#include "opennn/dataset/tabular_dataset.h"
#include "opennn/models/models.h"
#include "opennn/network/network.h"
#include "opennn/response_optimization/domain_contraction.h"
#include "opennn/response_optimization/genetic_response.h"
#include "opennn/response_optimization/response_optimization.h"
#include "opennn/training/training.h"

using namespace opennn;

namespace
{

vector<string> input_names = {"do3", "do4", "do5", "recycle", "wastage", "influent"};
const vector<string> output_names = {"lcow", "sec", "tss", "cod", "tn", "bod5", "nh4", "biogas"};

Index inputs_number = 6;
const Index outputs_number = 8;

bool has_input(const string& name)
{
    return ranges::find(input_names, name) != input_names.end();
}

using Sense = ResponseOptimization::Objective::Sense;
using Condition = ResponseOptimization::Constraint::Condition;


struct ObjectiveSpec
{
    string expression;
    Sense sense;
};


struct ConstraintSpec
{
    string expression;
    Condition condition;
    vector<float> values;
};


struct Scenario
{
    string name;
    string description;
    vector<ObjectiveSpec> objectives;
    vector<ConstraintSpec> constraints;
};


// The dataset file in <root>/data: bsm2_dataset.csv, or the one named on the command line
// (bsm2_dataset_infill.csv after an infill round).

string dataset_name = "bsm2_dataset.csv";

filesystem::path dataset_path(const filesystem::path& root)
{
    return root / "data" / dataset_name;
}


filesystem::path network_path(const filesystem::path& root)
{
    return root / "model" / "bsm2_network.json";
}


// The inputs are the dataset's columns before the first output (six, or seven with rain).

void read_input_names(const filesystem::path& root)
{
    ifstream file(dataset_path(root));
    string header;
    if (!getline(file, header)) return;
    if (!header.empty() && header.back() == '\r') header.pop_back();

    vector<string> names;
    stringstream stream(header);
    for (string cell; getline(stream, cell, ',');)
    {
        if (cell == output_names[0]) break;
        names.push_back(cell);
    }

    if (names.empty()) return;
    input_names = names;
    inputs_number = Index(names.size());
}


vector<Index> column_range(Index first, Index count)
{
    vector<Index> columns(static_cast<size_t>(count));
    for (Index i = 0; i < count; i++) columns[size_t(i)] = first + i;
    return columns;
}


// True coefficient of determination 1 - SSres/SStot for each output column.

VectorR determination(const MatrixR& targets, const MatrixR& outputs)
{
    VectorR r2(targets.cols());

    for (Index j = 0; j < targets.cols(); j++)
    {
        const double mean = targets.col(j).cast<double>().mean();
        const double ss_tot = (targets.col(j).cast<double>().array() - mean).square().sum();
        const double ss_res = (targets.col(j).cast<double>() - outputs.col(j).cast<double>()).array().square().sum();
        r2(j) = float(1.0 - ss_res/ss_tot);
    }

    return r2;
}


pair<MatrixR, MatrixR> split_rows(const MatrixR& data, const vector<Index>& rows)
{
    MatrixR inputs(Index(rows.size()), inputs_number);
    MatrixR targets(Index(rows.size()), outputs_number);

    for (Index i = 0; i < Index(rows.size()); i++)
    {
        inputs.row(i) = data.row(rows[size_t(i)]).leftCols(inputs_number);
        targets.row(i) = data.row(rows[size_t(i)]).segment(inputs_number, outputs_number);
    }

    return {inputs, targets};
}


vector<Scenario> make_scenarios();


Index output_column(const string& name)
{
    const auto found = ranges::find(output_names, name);
    return found == output_names.end() ? -1 : Index(found - output_names.begin());
}


bool is_output_bound(const ConstraintSpec& constraint)
{
    return output_column(constraint.expression) >= 0
        && (constraint.condition == Condition::LessEqual || constraint.condition == Condition::GreaterEqual);
}


// Back-off for an output bound: the 95th percentile of the absolute validation error among the
// samples whose true value lies within a factor of two of the bound, where the error matters.

pair<Index, float> validation_margin(const MatrixR& targets, const MatrixR& outputs, Index column, float bound)
{
    vector<float> errors;

    for (Index i = 0; i < targets.rows(); i++)
        if (targets(i, column) >= 0.5f*bound && targets(i, column) <= 2.0f*bound)
            errors.push_back(abs(outputs(i, column) - targets(i, column)));

    if (errors.empty()) return {0, 0.0f};

    ranges::sort(errors);

    return {Index(errors.size()), errors[size_t(ceil(0.95*double(errors.size()))) - 1]};
}


filesystem::path margins_path(const filesystem::path& root)
{
    return root / "model" / "constraint_margins.csv";
}


void write_margins(const filesystem::path& root, const MatrixR& targets, const MatrixR& outputs)
{
    ofstream file(margins_path(root));
    file << "output,bound,samples,margin\n" << setprecision(8);

    vector<pair<string, float>> written;

    for (const Scenario& scenario : make_scenarios())
        for (const ConstraintSpec& constraint : scenario.constraints)
        {
            if (!is_output_bound(constraint)) continue;

            const pair<string, float> key{constraint.expression, constraint.values[0]};
            if (ranges::find(written, key) != written.end()) continue;
            written.push_back(key);

            const auto [samples, margin] = validation_margin(targets, outputs, output_column(key.first), key.second);
            file << key.first << "," << key.second << "," << samples << "," << margin << "\n";
            cout << "  margin for " << key.first << " bound " << key.second << ": " << margin
                 << " (" << samples << " validation samples near the bound)" << endl;
        }
}


map<pair<string, float>, float> read_margins(const filesystem::path& root)
{
    map<pair<string, float>, float> margins;

    ifstream file(margins_path(root));
    string line;
    getline(file, line);

    while (getline(file, line))
    {
        stringstream stream(line);
        string name, bound, samples, margin;
        getline(stream, name, ',');
        getline(stream, bound, ',');
        getline(stream, samples, ',');
        getline(stream, margin, ',');
        margins[{name, stof(bound)}] = stof(margin);
    }

    return margins;
}


// The same scenario with every output bound tightened by its margin.

Scenario with_margins(Scenario scenario, const map<pair<string, float>, float>& margins)
{
    scenario.name += "_margin";
    scenario.description += ", output bounds backed off by their validation error";

    for (ConstraintSpec& constraint : scenario.constraints)
    {
        if (!is_output_bound(constraint)) continue;

        const float margin = margins.at({constraint.expression, constraint.values[0]});
        constraint.values[0] += constraint.condition == Condition::GreaterEqual ? margin : -margin;
    }

    return scenario;
}


void print_r2(const string& label, const VectorR& r2)
{
    cout << "  " << left << setw(12) << label;
    for (Index j = 0; j < r2.size(); j++)
        cout << " " << output_names[size_t(j)] << "=" << fixed << setprecision(4) << r2(j);
    cout << endl;
}


int train(const filesystem::path& root)
{
    TabularDataset dataset(dataset_path(root), ",", true, false);
    dataset.set_variable_indices(column_range(0, inputs_number), column_range(inputs_number, outputs_number));

    // Effluent total N and NH4 span two orders of magnitude (NH4 0.1 to 41 mg/L, the top near
    // nitrifier washout). A logarithmic scaler makes their error relative, which is what matters
    // at the 4 and 18 mg/L limits. Every other column keeps the default mean/deviation scaler.
    vector<string> scalers(size_t(inputs_number + outputs_number), "MeanStandardDeviation");
    scalers[size_t(inputs_number + output_column("tn"))] = "Logarithm";
    scalers[size_t(inputs_number + output_column("nh4"))] = "Logarithm";
    dataset.set_variable_scalers(scalers);

    set_seed(0);
    dataset.split_samples_random(0.70f, 0.15f, 0.15f);

    const MatrixR& data = dataset.get_data();

    const auto [validation_inputs, validation_targets] = split_rows(data, dataset.get_sample_indices(SampleRole::Validation));
    const auto [testing_inputs, testing_targets] = split_rows(data, dataset.get_sample_indices(SampleRole::Testing));

    cout << "Samples: " << data.rows()
         << " (training " << dataset.get_sample_indices(SampleRole::Training).size()
         << ", validation " << validation_inputs.rows()
         << ", testing " << testing_inputs.rows() << ")" << endl;

    // Optional settings, read from the environment (the defaults reproduce the toy's network):
    //   BSM2_NEURONS  hidden neurons to try, comma separated (8,16,24,32)
    //   BSM2_LAYERS   hidden layers of that size (1)
    //   BSM2_EPOCHS   quasi-Newton epochs (3000)
    //   BSM2_SELECT   "worst": largest worst-output validation R2 (default);
    //                 "nh4": smallest validation error of log NH4 where NH4 is 1 to 20 mg/L,
    //                 the range the effluent limit of 4 mg/L sits in
    const auto setting = [](const char* name, const string& fallback)
    {
        const char* value = getenv(name);
        return string(value && *value ? value : fallback);
    };

    vector<Index> neuron_counts;
    stringstream neuron_list(setting("BSM2_NEURONS", "8,16,24,32"));
    for (string cell; getline(neuron_list, cell, ',');) neuron_counts.push_back(stol(cell));
    const Index layers = stol(setting("BSM2_LAYERS", "1"));
    const Index epochs = stol(setting("BSM2_EPOCHS", "3000"));
    const bool select_nh4 = setting("BSM2_SELECT", "worst") == "nh4";

    const Index nh4 = output_column("nh4");

    const auto nh4_band_error = [&](const MatrixR& outputs)
    {
        double sum = 0.0;
        Index count = 0;
        for (Index i = 0; i < validation_targets.rows(); i++)
        {
            const float target = validation_targets(i, nh4);
            if (target < 1.0f || target > 20.0f) continue;
            sum += abs(log(double(max(outputs(i, nh4), 1.0e-3f))) - log(double(target)));
            count++;
        }
        return count ? float(sum/double(count)) : numeric_limits<float>::infinity();
    };

    float best_score = -numeric_limits<float>::infinity();
    Index best_neurons = 0;

    for (const Index neurons : neuron_counts)
    {
        set_seed(0);

        const vector<Index> hidden(size_t(layers), neurons);
        ApproximationNetwork network(dataset.get_input_shape(), Shape(hidden.begin(), hidden.end()), dataset.get_target_shape());

        Training training(&network, &dataset);
        training.set_loss("NormalizedSquaredError");
        training.get_loss()->set_regularization("L2");
        training.get_loss()->set_regularization_weight(1.0e-4f);
        training.set_optimization_algorithm("QuasiNewton");
        training.get_optimization_algorithm()->set_maximum_epochs(epochs);
        training.get_optimization_algorithm()->set_display(false);

        training.train();

        const MatrixR validation_outputs = network.calculate_outputs(validation_inputs);
        const VectorR validation_r2 = determination(validation_targets, validation_outputs);
        const float band_error = nh4_band_error(validation_outputs);

        print_r2(to_string(neurons) + " neurons", validation_r2);
        cout << "               log NH4 error, 1 to 20 mg/L: " << band_error << endl;

        const float score = select_nh4 ? -band_error : validation_r2.minCoeff();

        if (score > best_score)
        {
            best_score = score;
            best_neurons = neurons;
            network.save(network_path(root));
        }
    }

    cout << "Selected " << best_neurons << " hidden neurons in " << layers << " layer(s) ("
         << (select_nh4 ? "smallest validation log NH4 error, 1 to 20 mg/L" : "largest worst-output validation R2")
         << ")." << endl;

    Network network;
    network.load(network_path(root));

    write_margins(root, validation_targets, network.calculate_outputs(validation_inputs));

    const MatrixR testing_outputs = network.calculate_outputs(testing_inputs);

    print_r2("test", determination(testing_targets, testing_outputs));

    ofstream file(root / "results" / "test_predictions.csv");
    for (const string& name : input_names) file << name << ",";
    for (Index j = 0; j < outputs_number; j++)
        file << output_names[size_t(j)] << "," << output_names[size_t(j)] << "_predicted"
             << (j + 1 < outputs_number ? "," : "\n");
    file << setprecision(8);

    for (Index i = 0; i < testing_inputs.rows(); i++)
    {
        for (Index j = 0; j < inputs_number; j++) file << testing_inputs(i, j) << ",";
        for (Index j = 0; j < outputs_number; j++)
            file << testing_targets(i, j) << "," << testing_outputs(i, j) << (j + 1 < outputs_number ? "," : "\n");
    }

    ofstream summary(root / "model" / "training_summary.txt");
    summary << "dataset " << dataset_name << " (" << data.rows() << " rows)\n";
    summary << "hidden_neurons " << best_neurons << "\n";
    summary << "hidden_layers " << layers << "\n";
    const VectorR test_r2 = determination(testing_targets, testing_outputs);
    for (Index j = 0; j < outputs_number; j++)
        summary << "test_r2_" << output_names[size_t(j)] << " " << test_r2(j) << "\n";

    return 0;
}


// Writes the validation split train() used (same seed and fractions) with the saved network's
// predictions to <root>/results/validation_predictions.csv. The dashboard computes the safety
// margin of a bound the user sets from these errors, by the rule of validation_margin().

int validation(const filesystem::path& root)
{
    TabularDataset dataset(dataset_path(root), ",", true, false);
    dataset.set_variable_indices(column_range(0, inputs_number), column_range(inputs_number, outputs_number));

    set_seed(0);
    dataset.split_samples_random(0.70f, 0.15f, 0.15f);

    const auto [inputs, targets] = split_rows(dataset.get_data(), dataset.get_sample_indices(SampleRole::Validation));

    Network network;
    network.load(network_path(root));
    const MatrixR outputs = network.calculate_outputs(inputs);

    ofstream file(root / "results" / "validation_predictions.csv");
    for (const string& name : input_names) file << name << ",";
    for (Index j = 0; j < outputs_number; j++)
        file << output_names[size_t(j)] << "," << output_names[size_t(j)] << "_predicted"
             << (j + 1 < outputs_number ? "," : "\n");
    file << setprecision(8);

    for (Index i = 0; i < inputs.rows(); i++)
    {
        for (Index j = 0; j < inputs_number; j++) file << inputs(i, j) << ",";
        for (Index j = 0; j < outputs_number; j++)
            file << targets(i, j) << "," << outputs(i, j) << (j + 1 < outputs_number ? "," : "\n");
    }

    cout << "Wrote " << inputs.rows() << " validation predictions" << endl;

    return 0;
}


vector<Scenario> make_scenarios()
{
    // Every scenario keeps the BSM2 effluent limits (mg/L) at a fixed influent flow.

    const ConstraintSpec nominal{"influent", Condition::Equal, {20648.0f}};
    const vector<ConstraintSpec> limits = {
        {"tss", Condition::LessEqual, {30.0f}},
        {"cod", Condition::LessEqual, {100.0f}},
        {"tn", Condition::LessEqual, {18.0f}},
        {"bod5", Condition::LessEqual, {10.0f}},
        {"nh4", Condition::LessEqual, {4.0f}}};

    // With a rain input the scenarios are in dry weather (the sweep sets other rain flows).
    const auto with = [&](const ConstraintSpec& influent, bool nitrogen_limit = true)
    {
        vector<ConstraintSpec> constraints = {influent};
        if (has_input("rain")) constraints.push_back({"rain", Condition::Equal, {0.0f}});
        for (const ConstraintSpec& limit : limits)
            if (nitrogen_limit || limit.expression != "tn")
                constraints.push_back(limit);
        return constraints;
    };

    return {
        {"B1_min_lcow",
         "nominal influent: minimum LCOW within the effluent limits",
         {{"lcow", Sense::Minimize}},
         with(nominal)},

        {"B2_min_energy",
         "nominal influent: minimum SEC within the effluent limits",
         {{"sec", Sense::Minimize}},
         with(nominal)},

        {"B3_min_energy_low_load",
         "influent 17500 m3/d: minimum SEC within the effluent limits",
         {{"sec", Sense::Minimize}},
         with({"influent", Condition::Equal, {17500.0f}})},

        {"B4_min_energy_high_load",
         "influent 24000 m3/d: minimum SEC within the effluent limits",
         {{"sec", Sense::Minimize}},
         with({"influent", Condition::Equal, {24000.0f}})},

        {"B5_max_biogas",
         "nominal influent: maximum biogas within the effluent limits",
         {{"biogas", Sense::Maximize}},
         with(nominal)},

        {"B6_pareto_energy_nitrogen",
         "nominal influent: minimum SEC and minimum total N (Pareto front), other limits kept",
         {{"sec", Sense::Minimize}, {"tn", Sense::Minimize}},
         with(nominal, false)}
    };
}


void configure(ResponseOptimization& optimization, const Scenario& scenario)
{
    for (const ObjectiveSpec& objective : scenario.objectives)
        optimization.add_objective(objective.expression, objective.sense);

    for (const ConstraintSpec& constraint : scenario.constraints)
        optimization.add_constraint(constraint.expression, constraint.condition, constraint.values);

    optimization.set_iterations_number(20);
    optimization.set_points_number(1000);
}


void write_header(ofstream& file, bool with_scenario)
{
    if (with_scenario) file << "scenario,method,";
    for (const string& name : input_names) file << name << ",";
    for (Index j = 0; j < outputs_number; j++) file << output_names[size_t(j)] << (j + 1 < outputs_number ? "," : "\n");
}


void write_row(ofstream& file, const VectorR& row)
{
    for (Index j = 0; j < row.size(); j++) file << row(j) << (j + 1 < row.size() ? "," : "\n");
}


int optimize(const filesystem::path& root)
{
    Network network;
    network.load(network_path(root));

    const map<pair<string, float>, float> margins = read_margins(root);

    vector<Scenario> scenarios;
    for (const Scenario& scenario : make_scenarios())
    {
        scenarios.push_back(scenario);
        scenarios.push_back(with_margins(scenario, margins));
    }

    ofstream optima(root / "results" / "opennn_optima.csv");
    optima << setprecision(8);
    write_header(optima, true);

    for (const Scenario& scenario : scenarios)
    {
        cout << "\n" << scenario.name << ": " << scenario.description << endl;

        for (const string method : {"DomainContraction", "GeneticResponse"})
        {
            set_seed(1);

            unique_ptr<ResponseOptimization> optimization;
            if (method == "DomainContraction") optimization = make_unique<DomainContraction>(&network);
            else optimization = make_unique<GeneticResponse>(&network);

            configure(*optimization, scenario);

            MatrixR results;

            try
            {
                results = optimization->perform_response_optimization();
            }
            catch (const exception& e)
            {
                cout << "  " << method << ": " << e.what() << endl;
                continue;
            }

            if (scenario.objectives.size() == 1)
            {
                optima << scenario.name << "," << method << ",";
                write_row(optima, results.row(0).transpose());

                cout << "  " << left << setw(18) << method << fixed << setprecision(4);
                for (Index j = 0; j < inputs_number + outputs_number; j++)
                    cout << (j == inputs_number ? " |" : "") << " "
                         << (j < inputs_number ? input_names[size_t(j)] : output_names[size_t(j - inputs_number)])
                         << "=" << results(0, j);
                cout << endl;
            }
            else
            {
                ofstream front(root / "results" / ("pareto_" + scenario.name + "_" + method + ".csv"));
                front << setprecision(8);
                write_header(front, false);
                for (Index i = 0; i < results.rows(); i++)
                    write_row(front, results.row(i).transpose());

                const auto [advised_index, advised] = optimization->get_advised_point(results);

                optima << scenario.name << "," << method << "_advised,";
                write_row(optima, advised);

                cout << "  " << left << setw(18) << method << results.rows() << " front points; advised"
                     << fixed << setprecision(4) << " sec=" << advised(inputs_number + 1)
                     << " tn=" << advised(inputs_number + 4) << endl;
            }
        }
    }

    return 0;
}


// Optimal set-points over a grid of influent flows, for the dashboard in ../to_show: minimum energy
// (B2), minimum cost (B1) and maximum biogas (B5), each within the effluent limits backed off by
// their validation margins. Writes <root>/results/dashboard_optima.csv. A network with a rain input
// is swept over the rain flows in BSM2_RAIN_LEVELS (m3/d, comma separated; 0 by default) as well.

int sweep(const filesystem::path& root)
{
    Network network;
    network.load(network_path(root));

    const map<pair<string, float>, float> margins = read_margins(root);
    vector<pair<string, string>> objectives = {
        {"min_energy", "B2_min_energy"}, {"min_cost", "B1_min_lcow"}, {"max_biogas", "B5_max_biogas"}};

    // BSM2_SWEEP=min_energy (one objective) writes results/dashboard_optima_min_energy.csv, so the
    // objectives can run as parallel processes; the files are then joined.
    const char* only = getenv("BSM2_SWEEP");
    string file_name = "dashboard_optima.csv";
    if (only && *only)
    {
        erase_if(objectives, [&](const pair<string, string>& o) { return o.first != only; });
        throw_if(objectives.empty(), string("Unknown objective ") + only);
        file_name = "dashboard_optima_" + string(only) + ".csv";
    }

    vector<float> rain_levels = {0.0f};
    const char* levels = getenv("BSM2_RAIN_LEVELS");
    if (has_input("rain") && levels && *levels)
    {
        rain_levels.clear();
        stringstream list(levels);
        for (string cell; getline(list, cell, ',');) rain_levels.push_back(stof(cell));
    }

    ofstream file(root / "results" / file_name);
    file << setprecision(8) << "objective,";
    write_header(file, false);

    for (const auto& [objective, scenario_name] : objectives)
    {
        const vector<Scenario> scenarios = make_scenarios();
        const auto found = ranges::find_if(scenarios, [&](const Scenario& s) { return s.name == scenario_name; });
        throw_if(found == scenarios.end(), "Unknown scenario " + scenario_name);

        for (const float rain : rain_levels)
            for (float influent = 16600.0f; influent <= 24700.0f + 1.0f; influent += 300.0f)
            {
                Scenario scenario = *found;
                for (ConstraintSpec& constraint : scenario.constraints)
                {
                    if (constraint.expression == "influent") constraint.values = {influent};
                    if (constraint.expression == "rain") constraint.values = {rain};
                }
                scenario = with_margins(scenario, margins);

                set_seed(1);
                DomainContraction optimization(&network);
                configure(optimization, scenario);

                const string where = objective + (has_input("rain") ? " rain " + to_string(int(rain)) : "")
                                   + " influent " + to_string(int(influent));
                try
                {
                    const MatrixR results = optimization.perform_response_optimization();
                    file << objective << ",";
                    write_row(file, results.row(0).transpose());
                    file.flush();
                    cout << where << ": sec " << results(0, inputs_number + 1)
                         << " lcow " << results(0, inputs_number) << " nh4 " << results(0, inputs_number + 6) << endl;
                }
                catch (const exception& e)
                {
                    cout << where << ": " << e.what() << endl;
                }
            }
    }

    return 0;
}


// Writes every layer's parameters to <root>/model/parameters.json: per layer its label and, per
// parameter tensor, its shape and values. A rank-2 tensor is written row by row as OpenNN reads it
// in Dense::write_expression (as_matrix: rows = layer inputs, columns = layer outputs); a Dense
// layer's first tensor is its biases. Activations and scaling statistics are in the network JSON.

int export_parameters(const filesystem::path& root)
{
    Network network;
    network.load(network_path(root));

    ofstream file(root / "model" / "parameters.json");
    file << setprecision(9) << "{\"layers\": [";

    for (Index l = 0; l < network.get_layers_number(); l++)
    {
        const Layer& layer = *network.get_layers()[size_t(l)];
        const vector<TensorView>& views = layer.get_parameter_views();

        file << (l ? ",\n" : "\n") << "  {\"label\": \"" << layer.get_label() << "\", \"parameters\": [";

        for (size_t p = 0; p < views.size(); p++)
        {
            const TensorView& view = views[p];
            file << (p ? ", " : "") << "{\"shape\": [";
            for (Index d = 0; d < view.get_rank(); d++)
                file << (d ? ", " : "") << view.get_shape()[d];
            file << "], \"values\": [";

            if (view.get_rank() >= 2)
            {
                const auto matrix = view.as_matrix();
                for (Index r = 0; r < matrix.rows(); r++)
                {
                    file << (r ? ", [" : "[");
                    for (Index c = 0; c < matrix.cols(); c++)
                        file << (c ? ", " : "") << matrix(r, c);
                    file << "]";
                }
            }
            else
            {
                const float* values = view.as_float();
                for (Index i = 0; i < view.size(); i++)
                    file << (i ? ", " : "") << values[i];
            }

            file << "]}";
        }

        file << "]}";
    }

    file << "\n]}\n";

    cout << "Wrote " << (root / "model" / "parameters.json").string() << endl;

    return 0;
}


// Reads input rows (with a header) and writes them with the predicted outputs.

int predict(const filesystem::path& root, const filesystem::path& input_path, const filesystem::path& output_path)
{
    Network network;
    network.load(network_path(root));

    ifstream input(input_path);
    string line;
    getline(input, line);

    vector<vector<float>> rows;
    while (getline(input, line))
    {
        if (line.empty()) continue;
        vector<float> row(static_cast<size_t>(inputs_number));
        stringstream stream(line);
        string cell;
        for (float& value : row)
        {
            getline(stream, cell, ',');
            value = stof(cell);
        }
        rows.push_back(row);
    }

    MatrixR inputs(Index(rows.size()), inputs_number);
    for (Index i = 0; i < inputs.rows(); i++)
        for (Index j = 0; j < inputs_number; j++)
            inputs(i, j) = rows[size_t(i)][size_t(j)];

    const MatrixR outputs = network.calculate_outputs(inputs);

    ofstream file(output_path);
    file << setprecision(8);
    write_header(file, false);
    for (Index i = 0; i < inputs.rows(); i++)
    {
        VectorR row(inputs_number + outputs_number);
        row << inputs.row(i).transpose(), outputs.row(i).transpose();
        write_row(file, row);
    }

    return 0;
}

}


int main(int argc, char* argv[])
{
    try
    {
        const string mode = argc > 1 ? argv[1] : "";
        const filesystem::path root = argc > 2 ? argv[2] : ".";

        filesystem::create_directories(root / "model");
        filesystem::create_directories(root / "results");

        if ((mode == "train" || mode == "validation") && argc > 3) dataset_name = argv[3];
        read_input_names(root);

        if (mode == "train" || mode == "validation")
            return mode == "train" ? train(root) : validation(root);
        if (mode == "optimize") return optimize(root);
        if (mode == "predict" && argc > 4) return predict(root, argv[3], argv[4]);
        if (mode == "export") return export_parameters(root);
        if (mode == "sweep") return sweep(root);

        cerr << "Usage: bsm2_surrogate train|validation <root> [dataset file in <root>/data]\n"
                "       bsm2_surrogate optimize <root>\n"
                "       bsm2_surrogate predict <root> <inputs.csv> <outputs.csv>\n"
                "       bsm2_surrogate export <root>\n"
                "       bsm2_surrogate sweep <root>" << endl;
        return 2;
    }
    catch (const exception& e)
    {
        cerr << e.what() << endl;
        return 1;
    }
}
