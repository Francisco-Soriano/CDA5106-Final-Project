"""
Create copies of a base synthesis directory to be used for pareto curve generation
"""

import argparse
import os
import yaml

def parse_arguments():
    parser = argparse.ArgumentParser(description="Create a synthesis directory with specified parameters.")
    parser.add_argument("-o", "--synthesis_output_dir", type=str, required=True, help="Path to the location where the synthesis directory will be created")
    parser.add_argument("-s", "--base_synthesis_dir", type=str, required=True, help="Path to the synthesis scripts directory to be copied over")
    parser.add_argument("-d", "--design_config", type=str, required=True, help="Path to the design configuration file")
    return parser.parse_args()

def create_synthesis_directory(synthesis_output_dir, base_synthesis_dir, design_config):
    # Create the output directory if it doesn't exist
    synthesis_dir = os.path.join(synthesis_output_dir, "synthesis")
    os.makedirs(synthesis_dir, exist_ok=True)
    print(f"Synthesis directory created at: {synthesis_dir}")
    
    if not os.path.exists(design_config):
        raise FileNotFoundError(f"Design configuration file not found: {design_config}")
    
    design_configs = yaml.safe_load(open(design_config))
    
    for design in design_configs["designs"]:
        design_synthesis_dir = os.path.join(synthesis_dir, design)
        
        # Copy base synthesis scripts to the output directory
        os.system(f"cp -r {base_synthesis_dir} {design_synthesis_dir}")
        print(f"Copied synthesis scripts for design '{design}' to: {design_synthesis_dir}")
    
    
def main():
    args = parse_arguments()
    create_synthesis_directory(args.synthesis_output_dir, args.base_synthesis_dir, args.design_config)
    
if __name__ == "__main__":
    main()
    