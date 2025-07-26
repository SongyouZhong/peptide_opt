openmpnn_dir="./ProteinMPNN/"
openmpnn_helper="${openmpnn_dir}helper_scripts/"
chains_to_design="A"

for i in $(seq 1 10)
do
    output_dir="./pmpnn/complex$i"
    path_for_parsed_chains="${output_dir}/parsed_pdbs.jsonl"
    path_for_assigned_chains="${output_dir}/assigned_pdbs.jsonl"

    python3.10 ${openmpnn_helper}parse_multiple_chains.py --input_path="$output_dir" --output_path="$path_for_parsed_chains"

    python3.10 ${openmpnn_helper}assign_fixed_chains.py \
        --input_path="$path_for_parsed_chains" \
        --output_path="$path_for_assigned_chains" \
        --chain_list $chains_to_design

    python3.10 ${openmpnn_dir}protein_mpnn_run.py \
        --jsonl_path "$path_for_parsed_chains" \
        --out_folder "$output_dir" \
        --chain_id_jsonl "$path_for_assigned_chains" \
        --num_seq_per_target 10 \
        --sampling_temp 0.1 \
        --seed 37 \
        --batch_size 1

    echo "complex$i is done"
done

