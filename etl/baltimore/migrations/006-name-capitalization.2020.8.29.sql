-- K527, K508, T985
update officers set first_name = initcap(first_name), middle_initial = initcap(middle_initial), last_name = initcap(last_name) where character_length(last_name) > 2 and last_name ~ E'^[-\'[:upper:]]+$';