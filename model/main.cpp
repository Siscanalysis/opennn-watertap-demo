// Water treatment toy example: an OpenNN surrogate of the WaterTAP reverse osmosis
// flowsheet with a pressure exchanger, and response optimization on that surrogate.
//
//   ro_surrogate train    <root>   trains on <root>/data/ro_dataset.csv, writes <root>/model/
//   ro_surrogate optimize <root>   runs the scenarios on the saved network, writes <root>/results/
//   ro_surrogate predict  <root> <inputs.csv> <outputs.csv>   evaluates the saved network
//   ro_surrogate export   <root>   writes the trained parameters to <root>/model/parameters.json
//   ro_surrogate sweep    <root>   optimal set-points over a salinity grid, for the dashboard
//   ro_surrogate validation <root> the validation split's targets and predictions, for the dashboard
//
// Inputs:  salinity (g/kg), recovery (-), pressure (bar)
// Outputs: lcow ($/m3), sec (kWh/m3), permeate_ppm (mg/kg), flux_out (outlet water flux, kg/m2/h),
//          flux_avg (average water flux, kg/m2/h), area (m2)
//
// The scenarios are mirrored in verify_optima.py, which checks every answer against WaterTAP.

#include <algorithm>
#include <array>
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

const vector<string> input_names = {"salinity", "recovery", "pressure"};
const vector<string> output_names = {"lcow", "sec", "permeate_ppm", "flux_out", "flux_avg", "area"};

const Index inputs_number = 3;
const Index outputs_number = 6;

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
    bool domain_guard = true;
};


filesystem::path dataset_path(const filesystem::path& root)
{
    return root / "data" / "ro_dataset.csv";
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
    dataset.set_variable_indices({0, 1, 2}, {3, 4, 5, 6, 7, 8});

    set_seed(0);
    dataset.split_samples_random(0.70f, 0.15f, 0.15f);

    const MatrixR& data = dataset.get_data();

    const auto [validation_inputs, validation_targets] = split_rows(data, dataset.get_sample_indices(SampleRole::Validation));
    const auto [testing_inputs, testing_targets] = split_rows(data, dataset.get_sample_indices(SampleRole::Testing));

    cout << "Samples: " << data.rows()
         << " (training " << dataset.get_sample_indices(SampleRole::Training).size()
         << ", validation " << validation_inputs.rows()
         << ", testing " << testing_inputs.rows() << ")" << endl;

    const vector<Index> neuron_counts = {8, 16, 24, 32};

    float best_score = -numeric_limits<float>::infinity();
    Index best_neurons = 0;

    for (const Index neurons : neuron_counts)
    {
        set_seed(0);

        ApproximationNetwork network(dataset.get_input_shape(), {neurons}, dataset.get_target_shape());

        Training training(&network, &dataset);
        training.set_loss("NormalizedSquaredError");
        training.get_loss()->set_regularization("L2");
        training.get_loss()->set_regularization_weight(1.0e-4f);
        training.set_optimization_algorithm("QuasiNewton");
        training.get_optimization_algorithm()->set_maximum_epochs(3000);
        training.get_optimization_algorithm()->set_display(false);

        training.train();

        const VectorR validation_r2 = determination(validation_targets, network.calculate_outputs(validation_inputs));

        print_r2(to_string(neurons) + " neurons", validation_r2);

        if (validation_r2.minCoeff() > best_score)
        {
            best_score = validation_r2.minCoeff();
            best_neurons = neurons;
            network.save(root / "model" / "ro_network.json");
        }
    }

    cout << "Selected " << best_neurons << " hidden neurons (largest worst-output validation R2)." << endl;

    Network network;
    network.load(root / "model" / "ro_network.json");

    write_margins(root, validation_targets, network.calculate_outputs(validation_inputs));

    const MatrixR testing_outputs = network.calculate_outputs(testing_inputs);

    print_r2("test", determination(testing_targets, testing_outputs));

    ofstream file(root / "results" / "test_predictions.csv");
    file << "salinity,recovery,pressure";
    for (const string& name : output_names) file << "," << name << "," << name << "_predicted";
    file << "\n" << setprecision(8);

    for (Index i = 0; i < testing_inputs.rows(); i++)
    {
        file << testing_inputs(i, 0) << "," << testing_inputs(i, 1) << "," << testing_inputs(i, 2);
        for (Index j = 0; j < outputs_number; j++)
            file << "," << testing_targets(i, j) << "," << testing_outputs(i, j);
        file << "\n";
    }

    ofstream summary(root / "model" / "training_summary.txt");
    summary << "hidden_neurons " << best_neurons << "\n";
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
    dataset.set_variable_indices({0, 1, 2}, {3, 4, 5, 6, 7, 8});

    set_seed(0);
    dataset.split_samples_random(0.70f, 0.15f, 0.15f);

    const auto [inputs, targets] = split_rows(dataset.get_data(), dataset.get_sample_indices(SampleRole::Validation));

    Network network;
    network.load(root / "model" / "ro_network.json");
    const MatrixR outputs = network.calculate_outputs(inputs);

    ofstream file(root / "results" / "validation_predictions.csv");
    file << "salinity,recovery,pressure";
    for (const string& name : output_names) file << "," << name << "," << name << "_predicted";
    file << "\n" << setprecision(8);

    for (Index i = 0; i < inputs.rows(); i++)
    {
        file << inputs(i, 0) << "," << inputs(i, 1) << "," << inputs(i, 2);
        for (Index j = 0; j < outputs_number; j++)
            file << "," << targets(i, j) << "," << outputs(i, j);
        file << "\n";
    }

    cout << "Wrote " << inputs.rows() << " validation predictions" << endl;

    return 0;
}


// The sampled data cover pressures of at least 0.88 times the brine osmotic pressure.
// That pressure scales roughly with salinity/(1 - recovery), so pressure*(1 - recovery)/salinity
// measures the margin. Requiring it to stay above its smallest value in the data keeps the
// search where the surrogate was trained; the corner of the input box below it has no data.

float domain_guard_minimum(const filesystem::path& root)
{
    const TabularDataset dataset(dataset_path(root), ",", true, false);
    const MatrixR& data = dataset.get_data();

    float minimum = numeric_limits<float>::infinity();

    for (Index i = 0; i < data.rows(); i++)
        minimum = min(minimum, data(i, 2)*(1.0f - data(i, 1))/data(i, 0));

    return minimum;
}


vector<Scenario> make_scenarios()
{
    // Every scenario keeps WaterTAP's optimize_set_up limits: permeate <= 500 ppm,
    // outlet flux >= 1 kg/m2/h and pump outlet <= 80 bar (lower where stated).

    const ConstraintSpec seawater{"salinity", Condition::Equal, {35.0f}};
    const ConstraintSpec quality{"permeate_ppm", Condition::LessEqual, {500.0f}};
    const ConstraintSpec minimum_flux{"flux_out", Condition::GreaterEqual, {1.0f}};
    const ConstraintSpec pump_limit{"pressure", Condition::LessEqual, {80.0f}};

    return {
        {"S1_fixed_recovery",
         "35 g/kg, recovery 0.5: minimum LCOW (WaterTAP's own optimize_set_up problem)",
         {{"lcow", Sense::Minimize}},
         {seawater, {"recovery", Condition::Equal, {0.5f}}, quality, minimum_flux, pump_limit}},

        {"S2_free_recovery",
         "35 g/kg: minimum LCOW, recovery and pressure free",
         {{"lcow", Sense::Minimize}},
         {seawater, quality, minimum_flux, pump_limit}},

        {"S2b_free_recovery_no_guard",
         "S2 without the domain guard",
         {{"lcow", Sense::Minimize}},
         {seawater, quality, minimum_flux, pump_limit},
         false},

        {"S3_min_energy_design_flux",
         "35 g/kg: minimum SEC at an average flux of at least 20 kg/m2/h",
         {{"sec", Sense::Minimize}},
         {seawater, quality, minimum_flux, pump_limit, {"flux_avg", Condition::GreaterEqual, {20.0f}}}},

        // 44 rather than 45 g/kg: the search box is the training split's range, whose
        // largest salinity is just under the sampled 45 g/kg.
        {"S4_high_salinity",
         "44 g/kg: minimum LCOW with a 70 bar pump",
         {{"lcow", Sense::Minimize}},
         {{"salinity", Condition::Equal, {44.0f}}, quality, minimum_flux,
          {"pressure", Condition::LessEqual, {70.0f}}}},

        {"S5_max_recovery_budget",
         "35 g/kg: maximum recovery with LCOW of at most 0.420 $/m3",
         {{"recovery", Sense::Maximize}},
         {seawater, quality, minimum_flux, pump_limit, {"lcow", Condition::LessEqual, {0.420f}}}},

        {"S6_pareto_lcow_recovery",
         "35 g/kg: minimum LCOW and maximum recovery (Pareto front)",
         {{"lcow", Sense::Minimize}, {"recovery", Sense::Maximize}},
         {seawater, quality, minimum_flux, pump_limit}}
    };
}


void configure(ResponseOptimization& optimization, const Scenario& scenario, const float guard)
{
    for (const ObjectiveSpec& objective : scenario.objectives)
        optimization.add_objective(objective.expression, objective.sense);

    for (const ConstraintSpec& constraint : scenario.constraints)
        optimization.add_constraint(constraint.expression, constraint.condition, constraint.values);

    if (scenario.domain_guard)
        optimization.add_constraint("pressure*(1 - recovery)/salinity", Condition::GreaterEqual, {guard});

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
    network.load(root / "model" / "ro_network.json");

    const float guard = domain_guard_minimum(root);

    cout << "Domain guard: pressure*(1 - recovery)/salinity >= " << guard << endl;

    const map<pair<string, float>, float> margins = read_margins(root);

    vector<Scenario> scenarios;
    for (const Scenario& scenario : make_scenarios())
    {
        scenarios.push_back(scenario);
        if (scenario.domain_guard && ranges::any_of(scenario.constraints, is_output_bound))
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

            configure(*optimization, scenario, guard);

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
                     << fixed << setprecision(4) << " recovery=" << advised(1) << " pressure=" << advised(2)
                     << " | lcow=" << advised(3) << endl;
            }
        }
    }

    return 0;
}

// Optimal set-points over a grid of feed salinities, for the dashboard in to_show: minimum cost (S2)
// and minimum energy at an average flux of at least 20 kg/m2/h (S3), each with the output limits
// backed off by their validation margins and the domain guard on. Writes results/dashboard_optima.csv.

int sweep(const filesystem::path& root)
{
    Network network;
    network.load(root / "model" / "ro_network.json");

    const float guard = domain_guard_minimum(root);
    const map<pair<string, float>, float> margins = read_margins(root);
    const vector<pair<string, string>> objectives = {
        {"min_cost", "S2_free_recovery"}, {"min_energy", "S3_min_energy_design_flux"}};

    ofstream file(root / "results" / "dashboard_optima.csv");
    file << setprecision(8) << "objective,";
    write_header(file, false);

    for (const auto& [objective, scenario_name] : objectives)
    {
        const vector<Scenario> scenarios = make_scenarios();
        const auto found = ranges::find_if(scenarios, [&](const Scenario& s) { return s.name == scenario_name; });
        throw_if(found == scenarios.end(), "Unknown scenario " + scenario_name);

        for (float salinity = 26.0f; salinity <= 44.0f + 0.01f; salinity += 1.0f)
        {
            Scenario scenario = *found;
            for (ConstraintSpec& constraint : scenario.constraints)
                if (constraint.expression == "salinity") constraint.values = {salinity};
            scenario = with_margins(scenario, margins);

            set_seed(1);
            DomainContraction optimization(&network);
            configure(optimization, scenario, guard);

            try
            {
                const MatrixR results = optimization.perform_response_optimization();
                file << objective << ",";
                write_row(file, results.row(0).transpose());
                cout << objective << " salinity " << salinity << ": recovery " << results(0, 1)
                     << " pressure " << results(0, 2) << " lcow " << results(0, 3) << " sec " << results(0, 4) << endl;
            }
            catch (const exception& e)
            {
                cout << objective << " salinity " << salinity << ": " << e.what() << endl;
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
    network.load(root / "model" / "ro_network.json");

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


// Reads salinity,recovery,pressure rows (with a header) and writes them with the predicted outputs.

int predict(const filesystem::path& root, const filesystem::path& input_path, const filesystem::path& output_path)
{
    Network network;
    network.load(root / "model" / "ro_network.json");

    ifstream input(input_path);
    string line;
    getline(input, line);

    vector<std::array<float, 3>> rows;
    while (getline(input, line))
    {
        if (line.empty()) continue;
        std::array<float, 3> row{};
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

        if (mode == "train") return train(root);
        if (mode == "optimize") return optimize(root);
        if (mode == "predict" && argc > 4) return predict(root, argv[3], argv[4]);
        if (mode == "export") return export_parameters(root);
        if (mode == "sweep") return sweep(root);
        if (mode == "validation") return validation(root);

        cerr << "Usage: ro_surrogate train|optimize|export|sweep|validation <root>\n"
                "       ro_surrogate predict <root> <inputs.csv> <outputs.csv>" << endl;
        return 2;
    }
    catch (const exception& e)
    {
        cerr << e.what() << endl;
        return 1;
    }
}
