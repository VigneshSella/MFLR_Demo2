import numpy as np
import pandas as pd
import joblib
import os

# Paths to models and template
MF_MODEL_PATH = 'models/MF_clf.pkl'
SF_MODEL_PATH = 'models/HF_clf.pkl'
TEMPLATE_FILE_PATH = 'render_data/template.dat'
OUTPUT_DIR = 'render_data'

# Load the pre-trained models at startup
mf_pipeline = joblib.load(MF_MODEL_PATH)
sf_pipeline = joblib.load(SF_MODEL_PATH)

# Function to load and update pressure data
def update_pressure_file(pressure_data, output_filename):
    # Load the template file and read into a DataFrame
    raw_data = pd.read_table(TEMPLATE_FILE_PATH, delim_whitespace=True, header=None, skiprows=12, nrows=55966)
    raw_data.columns = ["x", "y", "z", "Cp", "Rho", "U", "V", "W", "Pressure"]
    
    # Replace pressure values with predicted data
    for i in range(len(pressure_data)):
        raw_data['Pressure'].iat[i] = pressure_data[i]

    # Convert pressure data to sea-level conditions
    a = (1.4 * 287 * 288.15) ** 0.5  # speed of sound at sea level
    q_inf = 1.225 * a ** 2  # dynamic pressure at sea level
    raw_data['Pressure'] = raw_data['Pressure'] * q_inf

    # Read the template file into a list of lines
    with open(TEMPLATE_FILE_PATH, 'r') as f:
        template_lines = f.readlines()
    
    # Path for the output file
    output_file_path = os.path.join(OUTPUT_DIR, output_filename)

    # Write the first 12 lines of the template to the output file
    with open(output_file_path, 'w') as f:
        f.writelines(template_lines[:12])

    # Append the modified DataFrame to the output file without headers or indices
    raw_data.to_csv(output_file_path, mode='a', index=False, header=False, sep=' ')

    # Append the remaining lines from the template to the output file
    with open(output_file_path, 'a') as f:
        f.writelines(template_lines[55978:])

    return output_file_path

# Define prediction functions that use the loaded pipelines
def multifidelity_regression(mach, alpha, beta):
    input_data = np.array([[mach, alpha, beta]])
    pressure_data = mf_pipeline.predict(input_data).flatten()  # Get the pressure values as a flat array
    output_file = update_pressure_file(pressure_data, 'MF_prediction.dat')
    return pressure_data, output_file

def singlefidelity_regression(mach, alpha, beta):
    input_data = np.array([[mach, alpha, beta]])
    pressure_data = sf_pipeline.predict(input_data).flatten()  # Get the pressure values as a flat array
    output_file = update_pressure_file(pressure_data, 'SF_prediction.dat')
    return pressure_data, output_file