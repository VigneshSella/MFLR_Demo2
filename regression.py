import numpy as np
import pandas as pd
import joblib
import os
import pickle

# Paths to models and template
MF_MODEL_PATH = 'models/MF_clf.pkl'
SF_MODEL_PATH = 'models/HF_clf.pkl'
POD_PATH = 'models/POD.pkl'
TEMPLATE_FILE_PATH = 'render_data/template.dat'
OUTPUT_DIR = 'render_data'

# Load the pre-trained models at startup
mf_pipeline = joblib.load(MF_MODEL_PATH)
sf_pipeline = joblib.load(SF_MODEL_PATH)

# Function to load and update pressure data
def update_pressure_file(pressure_data, output_file_path):
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
    # Scale Mach, alpha, and beta values between 0 and 1.
    # Mach ranges from 5 to 7, alpha from 0 to 8, beta from 0 to 8 during model training.
    mach = (mach - 5) / 2
    alpha = alpha / 8
    beta = beta / 8
    # print(f"Scaled inputs: mach={mach}, alpha={alpha}, beta={beta}")
    # Load U_POD and Y_MEAN from POD.pkl using pickle not joblib
    with open(POD_PATH, 'rb') as f:
        data = pickle.load(f)
    U_POD = data['U_POD'] 
    Y_MEAN = data['Y_MEAN']
    input_data = np.array([[mach, alpha, beta]])
    pressure_data = mf_pipeline.predict(input_data)@U_POD.T + Y_MEAN
    # print("Computed pressure data")
    pressure_data = pressure_data.flatten()
    # Path for the output file
    output_file_path = os.path.join(OUTPUT_DIR, 'MF_prediction.dat')
    output_file = update_pressure_file(pressure_data, output_file_path)
    # print("Updated output file")
    return pressure_data, output_file

def singlefidelity_regression(mach, alpha, beta):
    # Scale Mach, alpha, and beta values between 0 and 1.
    # Mach ranges from 5 to 7, alpha from 0 to 8, beta from 0 to 8 during model training.
    mach = (mach - 5) / 2
    alpha = alpha / 8
    beta = beta / 8
    # print(f"Scaled inputs: mach={mach}, alpha={alpha}, beta={beta}")
    # Load U_POD and Y_MEAN from POD.pkl using pickle not joblib
    with open(POD_PATH, 'rb') as f:
        data = pickle.load(f)
    U_POD = data['U_POD'] 
    Y_MEAN = data['Y_MEAN']
    input_data = np.array([[mach, alpha, beta]])
    pressure_data = sf_pipeline.predict(input_data)@U_POD.T + Y_MEAN
    # print("Computed pressure data")
    pressure_data = pressure_data.flatten()
    # Path for the output file
    output_file_path = os.path.join(OUTPUT_DIR, 'SF_prediction.dat')
    output_file = update_pressure_file(pressure_data, output_file_path)
    # print("Updated output file")
    return pressure_data, output_file