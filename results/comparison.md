Gap: how much worse WaterTAP's value at the OpenNN point is than WaterTAP's best optimum (negative = better, which only an infeasible point can be unless WaterTAP's optimum is local).
Feasible: the nominal constraints hold in WaterTAP within 0.1 %.

| Scenario | Method | Recovery | Pressure (bar) | Objective | OpenNN predicted | WaterTAP at that point | WaterTAP optimum | Gap | Feasible in WaterTAP |
|---|---|---:|---:|---|---:|---:|---:|---:|---|
| S1_fixed_recovery | DomainContraction | 0.5000 | 58.31 | lcow | 0.4141 | 0.4155 | 0.4155 | -0.01 % | no (flux_out>= by 2.50 %) |
| S1_fixed_recovery | GeneticResponse | 0.5000 | 58.31 | lcow | 0.4141 | 0.4155 | 0.4155 | -0.01 % | no (flux_out>= by 2.50 %) |
| S1_fixed_recovery_margin | DomainContraction | 0.5000 | 60.24 | lcow | 0.4149 | 0.4164 | 0.4155 | +0.22 % | yes |
| S1_fixed_recovery_margin | GeneticResponse | 0.5000 | 60.24 | lcow | 0.4149 | 0.4164 | 0.4155 | +0.22 % | yes |
| S2_free_recovery | DomainContraction | 0.5228 | 60.41 | lcow | 0.4131 | 0.4142 | 0.4147 | -0.12 % | no (flux_out>= by 7.78 %) |
| S2_free_recovery | GeneticResponse | 0.5227 | 60.40 | lcow | 0.4131 | 0.4142 | 0.4147 | -0.12 % | no (flux_out>= by 7.78 %) |
| S2_free_recovery_margin | DomainContraction | 0.5051 | 60.74 | lcow | 0.4149 | 0.4163 | 0.4147 | +0.40 % | yes |
| S2_free_recovery_margin | GeneticResponse | 0.5046 | 60.69 | lcow | 0.4149 | 0.4163 | 0.4147 | +0.40 % | yes |
| S2b_free_recovery_no_guard | DomainContraction | 0.5225 | 60.38 | lcow | 0.4131 | 0.4142 | 0.4147 | -0.12 % | no (flux_out>= by 7.70 %) |
| S2b_free_recovery_no_guard | GeneticResponse | 0.5222 | 60.34 | lcow | 0.4131 | 0.4142 | 0.4147 | -0.12 % | no (flux_out>= by 7.68 %) |
| S3_min_energy_design_flux | DomainContraction | 0.3672 | 56.77 | sec | 2.3006 | 2.2916 | 2.2843 | +0.32 % | yes |
| S3_min_energy_design_flux | GeneticResponse | 0.3675 | 56.78 | sec | 2.3005 | 2.2916 | 2.2843 | +0.32 % | yes |
| S3_min_energy_design_flux_margin | DomainContraction | 0.3661 | 57.02 | sec | 2.3084 | 2.2993 | 2.2843 | +0.65 % | yes |
| S3_min_energy_design_flux_margin | GeneticResponse | 0.3648 | 56.97 | sec | 2.3084 | 2.2989 | 2.2843 | +0.64 % | yes |
| S4_high_salinity | DomainContraction | 0.4773 | 69.98 | lcow | 0.4697 | 0.4700 | 0.4702 | -0.05 % | no (flux_out>= by 2.52 %) |
| S4_high_salinity | GeneticResponse | 0.4775 | 70.00 | lcow | 0.4697 | 0.4699 | 0.4702 | -0.05 % | no (flux_out>= by 2.65 %) |
| S4_high_salinity_margin | DomainContraction | 0.4558 | 69.98 | lcow | 0.4726 | 0.4729 | 0.4702 | +0.59 % | yes |
| S4_high_salinity_margin | GeneticResponse | 0.4560 | 70.00 | lcow | 0.4726 | 0.4729 | 0.4702 | +0.59 % | yes |
| S5_max_recovery_budget | DomainContraction | 0.5785 | 67.28 | recovery | 0.5785 | 0.5785 | 0.5709 | -1.33 % | no (flux_out>= by 11.58 %) |
| S5_max_recovery_budget | GeneticResponse | 0.5785 | 67.28 | recovery | 0.5785 | 0.5785 | 0.5709 | -1.33 % | no (flux_out>= by 11.58 %) |
| S5_max_recovery_budget_margin | DomainContraction | 0.5456 | 65.30 | recovery | 0.5456 | 0.5456 | 0.5709 | +4.44 % | yes |
| S5_max_recovery_budget_margin | GeneticResponse | 0.5455 | 65.30 | recovery | 0.5455 | 0.5455 | 0.5709 | +4.45 % | yes |
| S6_pareto_lcow_recovery | DomainContraction_advised | 0.5740 | 66.63 | lcow | 0.4189 | 0.4188 | n/a |  | no (flux_out>= by 11.45 %) |
| S6_pareto_lcow_recovery | GeneticResponse_advised | 0.5678 | 65.75 | lcow | 0.4176 | 0.4175 | n/a |  | no (flux_out>= by 11.50 %) |
| S6_pareto_lcow_recovery_margin | DomainContraction_advised | 0.5651 | 67.96 | lcow | 0.4224 | 0.4226 | n/a |  | yes |
| S6_pareto_lcow_recovery_margin | GeneticResponse_advised | 0.5600 | 67.23 | lcow | 0.4211 | 0.4214 | n/a |  | yes |

WaterTAP optima:

| Scenario | Run | Recovery | Pressure (bar) | LCOW | SEC | Permeate (ppm) | Outlet flux | Average flux | Area (m2) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1_fixed_recovery | fixed recovery **(best)** | 0.5000 | 58.46 | 0.4155 | 2.2498 | 379.1 | 1.000 | 17.65 | 100.5 |
| S2_free_recovery | start 0.38 | 0.5209 | 60.68 | 0.4147 | 2.3040 | 364.6 | 1.000 | 18.93 | 97.6 |
| S2_free_recovery | start 0.5 | 0.5209 | 60.68 | 0.4147 | 2.3040 | 364.6 | 1.000 | 18.93 | 97.6 |
| S2_free_recovery | start 0.58 **(best)** | 0.5209 | 60.68 | 0.4147 | 2.3040 | 364.6 | 1.000 | 18.93 | 97.6 |
| S2_free_recovery | grid best, then free | 0.5209 | 60.68 | 0.4147 | 2.3040 | 364.6 | 1.000 | 18.93 | 97.6 |
| S2_free_recovery | best grid point | 0.5250 | 61.15 | 0.4147 | 2.3160 | 361.8 | 1.000 | 19.20 | 97.0 |
| S2b_free_recovery_no_guard | start 0.38 | 0.5209 | 60.68 | 0.4147 | 2.3040 | 364.6 | 1.000 | 18.93 | 97.6 |
| S2b_free_recovery_no_guard | start 0.5 | 0.5209 | 60.68 | 0.4147 | 2.3040 | 364.6 | 1.000 | 18.93 | 97.6 |
| S2b_free_recovery_no_guard | start 0.58 **(best)** | 0.5209 | 60.68 | 0.4147 | 2.3040 | 364.6 | 1.000 | 18.93 | 97.6 |
| S2b_free_recovery_no_guard | grid best, then free | 0.5209 | 60.68 | 0.4147 | 2.3040 | 364.6 | 1.000 | 18.93 | 97.6 |
| S2b_free_recovery_no_guard | best grid point | 0.5250 | 61.15 | 0.4147 | 2.3160 | 361.8 | 1.000 | 19.20 | 97.0 |
| S3_min_energy_design_flux | start 0.38 | 0.5370 | 62.55 | 0.4152 | 2.3528 | 353.9 | 1.000 | 20.00 | 95.3 |
| S3_min_energy_design_flux | start 0.5 | 0.5370 | 62.55 | 0.4152 | 2.3528 | 353.9 | 1.000 | 20.00 | 95.3 |
| S3_min_energy_design_flux | start 0.58 | 0.5370 | 62.55 | 0.4152 | 2.3528 | 353.9 | 1.000 | 20.00 | 95.3 |
| S3_min_energy_design_flux | grid best, then free | 0.5370 | 62.55 | 0.4152 | 2.3528 | 353.9 | 1.000 | 20.00 | 95.3 |
| S3_min_energy_design_flux | best grid point **(best)** | 0.3500 | 56.01 | 0.4238 | 2.2843 | 313.1 | 8.510 | 20.00 | 62.1 |
| S4_high_salinity | start 0.38 **(best)** | 0.4760 | 70.00 | 0.4702 | 2.6866 | 443.4 | 1.000 | 18.65 | 90.3 |
| S4_high_salinity | start 0.5 | 0.4760 | 70.00 | 0.4702 | 2.6866 | 443.4 | 1.000 | 18.65 | 90.3 |
| S4_high_salinity | start 0.58 | 0.4760 | 70.00 | 0.4702 | 2.6866 | 443.4 | 1.000 | 18.65 | 90.3 |
| S4_high_salinity | grid best, then free | 0.4760 | 70.00 | 0.4702 | 2.6866 | 443.4 | 1.000 | 18.65 | 90.3 |
| S4_high_salinity | best grid point | 0.4750 | 69.88 | 0.4702 | 2.6837 | 444.4 | 1.000 | 18.59 | 90.4 |
| S5_max_recovery_budget | start 0.38 | 0.5709 | 67.04 | 0.4200 | 2.4780 | 332.2 | 1.000 | 22.55 | 89.8 |
| S5_max_recovery_budget | start 0.5 **(best)** | 0.5709 | 67.04 | 0.4200 | 2.4780 | 332.2 | 1.000 | 22.55 | 89.8 |
| S5_max_recovery_budget | start 0.58 | 0.5709 | 67.04 | 0.4200 | 2.4780 | 332.2 | 1.000 | 22.55 | 89.8 |
| S5_max_recovery_budget | grid best, then free | 0.5709 | 67.04 | 0.4200 | 2.4780 | 332.2 | 1.000 | 22.55 | 89.8 |
| S5_max_recovery_budget | best grid point | 0.5625 | 66.22 | 0.4191 | 2.4559 | 335.5 | 1.057 | 22.11 | 90.3 |

- Pareto front DomainContraction: 100 points, 1 feasible in WaterTAP; true LCOW of the feasible ones above WaterTAP's minimum at the same recovery: median +0.92 %, worst +0.92 %.
- Pareto front GeneticResponse: 100 points, 0 feasible in WaterTAP; true LCOW of the feasible ones above WaterTAP's minimum at the same recovery: none feasible.
- Pareto front margin_DomainContraction: 100 points, 100 feasible in WaterTAP; true LCOW of the feasible ones above WaterTAP's minimum at the same recovery: median +0.88 %, worst +1.94 %.
- Pareto front margin_GeneticResponse: 100 points, 100 feasible in WaterTAP; true LCOW of the feasible ones above WaterTAP's minimum at the same recovery: median +0.84 %, worst +1.15 %.
