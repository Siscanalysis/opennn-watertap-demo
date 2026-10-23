Gap: how much worse WaterTAP's value at the OpenNN point is than WaterTAP's best optimum (negative = better, which only an infeasible point can be unless WaterTAP's optimum is local).
Feasible: the BSM2 effluent limits hold in WaterTAP within 0.1 % (total N excluded for the Pareto scenario).

| Scenario | Method | DO3 | DO4 | DO5 | Recycle | Wastage | Objective | OpenNN predicted | WaterTAP at that point | WaterTAP optimum | Gap | Feasible in WaterTAP |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| B1_min_lcow | DomainContraction | 0.50 | 0.63 | 1.08 | 0.305 | 0.0170 | lcow | 0.3609 | 0.3611 | 0.3607 | +0.11 % | yes (cod by 0.0 %) |
| B1_min_lcow | GeneticResponse | 0.50 | 0.63 | 1.08 | 0.310 | 0.0170 | lcow | 0.3609 | 0.3611 | 0.3607 | +0.11 % | no (nh4 by 0.7 %) |
| B1_min_lcow_margin | DomainContraction | 0.51 | 1.06 | 1.23 | 0.383 | 0.0178 | lcow | 0.3619 | 0.3620 | 0.3607 | +0.35 % | yes |
| B1_min_lcow_margin | GeneticResponse | 0.50 | 0.83 | 1.38 | 0.300 | 0.0178 | lcow | 0.3619 | 0.3620 | 0.3607 | +0.34 % | yes |
| B2_min_energy | DomainContraction | 0.59 | 0.72 | 1.21 | 0.800 | 0.0172 | sec | 0.2838 | 0.2852 | 0.2823 | +1.03 % | yes (cod by 0.0 %) |
| B2_min_energy | GeneticResponse | 0.50 | 0.82 | 1.22 | 0.800 | 0.0172 | sec | 0.2838 | 0.2853 | 0.2823 | +1.07 % | yes (cod by 0.0 %) |
| B2_min_energy_margin | DomainContraction | 0.94 | 1.05 | 1.25 | 0.797 | 0.0179 | sec | 0.2938 | 0.2938 | 0.2823 | +4.07 % | yes |
| B2_min_energy_margin | GeneticResponse | 0.92 | 1.12 | 1.20 | 0.800 | 0.0179 | sec | 0.2937 | 0.2937 | 0.2823 | +4.03 % | yes |
| B3_min_energy_low_load | DomainContraction | 0.51 | 0.50 | 0.51 | 0.797 | 0.0160 | sec | 0.2829 | 0.2819 | 0.2822 | -0.09 % | no (nh4 by 4.3 %) |
| B3_min_energy_low_load | GeneticResponse | 0.50 | 0.50 | 0.50 | 0.800 | 0.0160 | sec | 0.2827 | 0.2817 | 0.2822 | -0.19 % | no (nh4 by 6.6 %) |
| B3_min_energy_low_load_margin | DomainContraction | 0.50 | 0.51 | 0.69 | 0.800 | 0.0152 | sec | 0.2863 | 0.2866 | 0.2822 | +1.57 % | yes |
| B3_min_energy_low_load_margin | GeneticResponse | 0.50 | 0.51 | 0.69 | 0.800 | 0.0152 | sec | 0.2862 | 0.2866 | 0.2822 | +1.54 % | yes |
| B4_min_energy_high_load | DomainContraction | 1.20 | 1.49 | 1.39 | 0.592 | 0.0188 | sec | 0.2965 | 0.2987 | 0.2951 | +1.22 % | yes (cod by 0.0 %) |
| B4_min_energy_high_load | GeneticResponse | 1.22 | 1.48 | 1.34 | 0.567 | 0.0187 | sec | 0.2966 | 0.2990 | 0.2951 | +1.31 % | yes (cod by 0.0 %) |
| B4_min_energy_high_load_margin | DomainContraction | 1.44 | 1.67 | 1.83 | 0.303 | 0.0194 | sec | 0.3186 | 0.3186 | 0.2951 | +7.96 % | yes |
| B4_min_energy_high_load_margin | GeneticResponse | 1.43 | 1.69 | 1.81 | 0.300 | 0.0194 | sec | 0.3185 | 0.3185 | 0.2951 | +7.93 % | yes |
| B5_max_biogas | DomainContraction | 2.32 | 2.85 | 2.99 | 0.800 | 0.0250 | biogas | 1341.6287 | 1336.1333 | 1336.2721 | +0.01 % | yes |
| B5_max_biogas | GeneticResponse | 2.28 | 2.94 | 3.00 | 0.800 | 0.0250 | biogas | 1341.7321 | 1336.1838 | 1336.2721 | +0.01 % | yes |
| B5_max_biogas_margin | DomainContraction | 2.51 | 2.97 | 2.98 | 0.799 | 0.0250 | biogas | 1341.5643 | 1336.1738 | 1336.2721 | +0.01 % | yes |
| B5_max_biogas_margin | GeneticResponse | 2.42 | 3.00 | 3.00 | 0.800 | 0.0250 | biogas | 1341.6949 | 1336.1990 | 1336.2721 | +0.01 % | yes |
| B6_pareto_energy_nitrogen | DomainContraction_advised | 1.16 | 1.54 | 1.20 | 0.799 | 0.0173 | sec | 0.3040 | 0.3039 | n/a |  | yes |
| B6_pareto_energy_nitrogen | GeneticResponse_advised | 1.34 | 1.67 | 1.02 | 0.800 | 0.0173 | sec | 0.3069 | 0.3066 | n/a |  | yes |
| B6_pareto_energy_nitrogen_margin | DomainContraction_advised | 1.45 | 1.69 | 1.33 | 0.799 | 0.0179 | sec | 0.3111 | n/a | n/a |  | flowsheet failed |
| B6_pareto_energy_nitrogen_margin | GeneticResponse_advised | 1.59 | 1.70 | 1.02 | 0.800 | 0.0179 | sec | 0.3109 | 0.3105 | n/a |  | yes |

WaterTAP optima (IPOPT from the base case = start 0 and four Latin-hypercube starts):

| Scenario | Start | DO3 | DO4 | DO5 | Recycle | Wastage | LCOW | SEC | TSS | COD | TN | BOD5 | NH4 | Biogas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_min_lcow | 0 | 0.70 | 0.80 | 0.82 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B1_min_lcow | 1 | failed |||||||||||||
| B1_min_lcow | 2 | 0.70 | 0.80 | 0.82 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
| B1_min_lcow | 3 **(best)** | 0.70 | 0.80 | 0.82 | 0.800 | 0.0172 | 0.3607 | 0.2823 | 21.6 | 100.0 | 9.49 | 4.99 | 4.00 | 1249 |
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

- Pareto front DomainContraction: 25 checked points, 22 feasible in WaterTAP; true SEC above WaterTAP's minimum at the same total N: median +0.45 %, worst +4.65 %.
- Pareto front GeneticResponse: 25 checked points, 20 feasible in WaterTAP; true SEC above WaterTAP's minimum at the same total N: median +0.56 %, worst +14.89 %.
- Pareto front margin_DomainContraction: 25 checked points, 22 feasible in WaterTAP; true SEC above WaterTAP's minimum at the same total N: median +1.78 %, worst +7.84 %.
- Pareto front margin_GeneticResponse: 25 checked points, 22 feasible in WaterTAP; true SEC above WaterTAP's minimum at the same total N: median +2.25 %, worst +10.58 %.
