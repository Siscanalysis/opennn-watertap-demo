Gap: how much worse WaterTAP's value at the OpenNN point is than WaterTAP's best optimum (negative = better, which only an infeasible point can be unless WaterTAP's optimum is local).
Feasible: the BSM2 effluent limits hold in WaterTAP within 0.1 % (total N excluded for the Pareto scenario).

| Scenario | Method | DO3 | DO4 | DO5 | Recycle | Wastage | Objective | OpenNN predicted | WaterTAP at that point | WaterTAP optimum | Gap | Feasible in WaterTAP |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| B1_min_lcow | DomainContraction | 0.51 | 0.51 | 0.53 | 0.301 | 0.0169 | lcow | 0.3594 | 0.3583 | 0.3607 | -0.67 % | no (nh4 by 512.4 %) |
| B1_min_lcow | GeneticResponse | 0.50 | 0.51 | 0.54 | 0.301 | 0.0169 | lcow | 0.3594 | 0.3583 | 0.3607 | -0.67 % | no (nh4 by 512.9 %) |
| B1_min_lcow_margin | DomainContraction | 0.51 | 0.86 | 1.08 | 0.301 | 0.0176 | lcow | 0.3610 | 0.3616 | 0.3607 | +0.25 % | yes |
| B1_min_lcow_margin | GeneticResponse | 0.50 | 0.92 | 1.02 | 0.301 | 0.0176 | lcow | 0.3610 | 0.3616 | 0.3607 | +0.25 % | yes |
| B2_min_energy | DomainContraction | 0.52 | 0.52 | 0.52 | 0.307 | 0.0169 | sec | 0.2839 | 0.2566 | 0.2823 | -9.09 % | no (nh4 by 454.9 %) |
| B2_min_energy | GeneticResponse | 0.53 | 0.51 | 0.52 | 0.301 | 0.0169 | sec | 0.2841 | 0.2563 | 0.2823 | -9.21 % | no (nh4 by 462.9 %) |
| B2_min_energy_margin | DomainContraction | 0.51 | 0.88 | 1.05 | 0.303 | 0.0176 | sec | 0.2957 | 0.2926 | 0.2823 | +3.66 % | yes |
| B2_min_energy_margin | GeneticResponse | 0.50 | 0.83 | 1.11 | 0.301 | 0.0176 | sec | 0.2956 | 0.2925 | 0.2823 | +3.60 % | yes |
| B3_min_energy_low_load | DomainContraction | 0.50 | 0.52 | 0.52 | 0.797 | 0.0186 | sec | 0.2855 | 0.2743 | 0.2822 | -2.81 % | no (nh4 by 124.8 %) |
| B3_min_energy_low_load | GeneticResponse | 0.50 | 0.51 | 0.51 | 0.798 | 0.0185 | sec | 0.2854 | 0.2736 | 0.2822 | -3.04 % | no (nh4 by 136.2 %) |
| B3_min_energy_low_load_margin | DomainContraction | 0.51 | 0.51 | 0.51 | 0.794 | 0.0162 | sec | 0.2881 | 0.2820 | 0.2822 | -0.06 % | no (nh4 by 4.4 %) |
| B3_min_energy_low_load_margin | GeneticResponse | 0.50 | 0.51 | 0.51 | 0.798 | 0.0162 | sec | 0.2879 | n/a | 0.2822 |  | flowsheet failed |
| B4_min_energy_high_load | DomainContraction | 0.84 | 1.34 | 1.68 | 0.304 | 0.0184 | sec | 0.2954 | 0.3022 | 0.2951 | +2.40 % | no (cod by 0.2 %) |
| B4_min_energy_high_load | GeneticResponse | 0.88 | 1.30 | 1.67 | 0.301 | 0.0184 | sec | 0.2954 | 0.3025 | 0.2951 | +2.49 % | no (cod by 0.2 %) |
| B4_min_energy_high_load_margin | DomainContraction | 1.48 | 1.77 | 1.97 | 0.302 | 0.0193 | sec | 0.3223 | 0.3231 | 0.2951 | +9.47 % | yes |
| B4_min_energy_high_load_margin | GeneticResponse | 1.47 | 1.80 | 1.93 | 0.301 | 0.0193 | sec | 0.3222 | 0.3229 | 0.2951 | +9.43 % | yes |
| B5_max_biogas | DomainContraction | 2.35 | 3.00 | 2.47 | 0.656 | 0.0250 | biogas | 1339.9457 | 1335.9025 | 1336.2721 | +0.03 % | yes |
| B5_max_biogas | GeneticResponse | 2.31 | 3.00 | 2.52 | 0.650 | 0.0250 | biogas | 1339.9786 | 1335.9074 | 1336.2721 | +0.03 % | yes |
| B5_max_biogas_margin | DomainContraction | 2.82 | 2.96 | 2.51 | 0.566 | 0.0250 | biogas | 1339.3517 | 1335.7335 | 1336.2721 | +0.04 % | yes |
| B5_max_biogas_margin | GeneticResponse | 2.82 | 3.00 | 2.47 | 0.574 | 0.0250 | biogas | 1339.4188 | 1335.7583 | 1336.2721 | +0.04 % | yes |
| B6_pareto_energy_nitrogen | DomainContraction_advised | 0.73 | 1.46 | 1.21 | 0.797 | 0.0175 | sec | 0.3003 | 0.2966 | n/a |  | yes |
| B6_pareto_energy_nitrogen | GeneticResponse_advised | 0.50 | 1.30 | 1.16 | 0.798 | 0.0176 | sec | 0.2950 | 0.2905 | n/a |  | yes |
| B6_pareto_energy_nitrogen_margin | DomainContraction_advised | 0.81 | 1.44 | 1.17 | 0.797 | 0.0181 | sec | 0.2997 | 0.2959 | n/a |  | yes |
| B6_pareto_energy_nitrogen_margin | GeneticResponse_advised | 0.73 | 1.36 | 1.35 | 0.798 | 0.0181 | sec | 0.2998 | 0.2959 | n/a |  | yes |

WaterTAP optima (IPOPT from the base case = start 0 and four Latin-hypercube starts):

| Scenario | Start | DO3 | DO4 | DO5 | Recycle | Wastage | LCOW | SEC | TSS | COD | TN | BOD5 | NH4 | Biogas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_min_lcow | 0 | 0.70 | 0.80 | 0.82 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B1_min_lcow | 1 **(best)** | 0.70 | 0.80 | 0.82 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B1_min_lcow | 2 | 0.70 | 0.80 | 0.82 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B1_min_lcow | 3 | 0.70 | 0.80 | 0.82 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B1_min_lcow | 4 | 0.70 | 0.80 | 0.82 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B2_min_energy | 0 | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B2_min_energy | 1 **(best)** | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B2_min_energy | 2 | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B2_min_energy | 3 | 2.94 | 2.94 | 2.96 | 0.399 | 0.0226 | 0.3709 | 0.3957 | 18.3 | 97.7 | 14.44 | 4.43 | 1.42 | 1312 |
| B2_min_energy | 4 | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B3_min_energy_low_load | 0 | 0.50 | 0.50 | 0.50 | 0.800 | 0.0158 | 0.4022 | 0.2822 | 21.8 | 99.5 | 9.01 | 4.79 | 4.00 | 1043 |
| B3_min_energy_low_load | 1 | 0.50 | 0.50 | 0.50 | 0.800 | 0.0158 | 0.4022 | 0.2822 | 21.8 | 99.5 | 9.01 | 4.79 | 4.00 | 1043 |
| B3_min_energy_low_load | 2 | 0.50 | 0.50 | 0.50 | 0.800 | 0.0158 | 0.4022 | 0.2822 | 21.8 | 99.5 | 9.01 | 4.79 | 4.00 | 1043 |
| B3_min_energy_low_load | 3 **(best)** | 0.50 | 0.50 | 0.50 | 0.800 | 0.0158 | 0.4022 | 0.2822 | 21.8 | 99.5 | 9.01 | 4.79 | 4.00 | 1043 |
| B3_min_energy_low_load | 4 | 1.36 | 1.32 | 2.91 | 0.310 | 0.0222 | 0.4096 | 0.3457 | 17.8 | 96.8 | 14.62 | 4.17 | 1.04 | 1114 |
| B4_min_energy_high_load | 0 | failed |||||||||||||
| B4_min_energy_high_load | 1 | failed |||||||||||||
| B4_min_energy_high_load | 2 | 1.26 | 1.45 | 1.54 | 0.800 | 0.0188 | 0.3290 | 0.2951 | 21.2 | 100.0 | 9.87 | 5.09 | 4.00 | 1464 |
| B4_min_energy_high_load | 3 | failed |||||||||||||
| B4_min_energy_high_load | 4 **(best)** | 1.26 | 1.45 | 1.54 | 0.800 | 0.0188 | 0.3290 | 0.2951 | 21.2 | 100.0 | 9.87 | 5.09 | 4.00 | 1464 |
| B5_max_biogas | 0 **(best)** | 3.00 | 3.00 | 2.20 | 0.800 | 0.0250 | 0.3695 | 0.3641 | 17.1 | 97.0 | 9.10 | 4.24 | 3.29 | 1336 |
| B5_max_biogas | 1 | 3.00 | 3.00 | 2.20 | 0.800 | 0.0250 | 0.3695 | 0.3641 | 17.1 | 97.0 | 9.10 | 4.24 | 3.29 | 1336 |
| B5_max_biogas | 2 | failed |||||||||||||
| B5_max_biogas | 3 | 3.00 | 3.00 | 2.20 | 0.800 | 0.0250 | 0.3695 | 0.3641 | 17.1 | 97.0 | 9.10 | 4.24 | 3.29 | 1336 |
| B5_max_biogas | 4 | 3.00 | 3.00 | 2.20 | 0.800 | 0.0250 | 0.3695 | 0.3641 | 17.1 | 97.0 | 9.10 | 4.24 | 3.29 | 1336 |
| eps 6.0 | 0 | failed |||||||||||||
| eps 6.0 | 1 | failed |||||||||||||
| eps 6.5 | 0 | failed |||||||||||||
| eps 6.5 | 1 | failed |||||||||||||
| eps 7.0 | 0 | failed |||||||||||||
| eps 7.0 | 1 | failed |||||||||||||
| eps 7.5 | 0 | failed |||||||||||||
| eps 7.5 | 1 **(best)** | 1.52 | 1.75 | 2.19 | 0.800 | 0.0171 | 0.3637 | 0.3255 | 21.7 | 100.0 | 7.50 | 4.98 | 1.21 | 1247 |
| eps 8.0 | 0 **(best)** | 0.99 | 1.14 | 1.22 | 0.800 | 0.0172 | 0.3617 | 0.2965 | 21.7 | 100.0 | 8.00 | 4.98 | 2.05 | 1249 |
| eps 8.0 | 1 | 0.99 | 1.14 | 1.22 | 0.800 | 0.0172 | 0.3617 | 0.2965 | 21.7 | 100.0 | 8.00 | 4.98 | 2.05 | 1249 |
| eps 9.0 | 0 | 0.75 | 0.87 | 0.89 | 0.800 | 0.0172 | 0.3609 | 0.2850 | 21.6 | 100.0 | 9.00 | 4.99 | 3.39 | 1249 |
| eps 9.0 | 1 **(best)** | 0.75 | 0.87 | 0.89 | 0.800 | 0.0172 | 0.3609 | 0.2850 | 21.6 | 100.0 | 9.00 | 4.99 | 3.39 | 1249 |
| eps 10.0 | 0 **(best)** | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 10.0 | 1 | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 12.0 | 0 **(best)** | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 12.0 | 1 | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 14.0 | 0 **(best)** | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 14.0 | 1 | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 17.0 | 0 **(best)** | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 17.0 | 1 | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 21.0 | 0 **(best)** | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 21.0 | 1 | failed |||||||||||||
| eps 26.0 | 0 **(best)** | 0.69 | 0.81 | 0.83 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| eps 26.0 | 1 | failed |||||||||||||

- Pareto front DomainContraction: 25 checked points, 16 feasible in WaterTAP; true SEC above WaterTAP's minimum at the same total N: median +2.40 %, worst +6.12 %.
- Pareto front GeneticResponse: 25 checked points, 17 feasible in WaterTAP; true SEC above WaterTAP's minimum at the same total N: median +3.37 %, worst +9.77 %.
- Pareto front margin_DomainContraction: 25 checked points, 22 feasible in WaterTAP; true SEC above WaterTAP's minimum at the same total N: median +3.22 %, worst +8.52 %.
- Pareto front margin_GeneticResponse: 25 checked points, 20 feasible in WaterTAP; true SEC above WaterTAP's minimum at the same total N: median +7.53 %, worst +12.62 %.
