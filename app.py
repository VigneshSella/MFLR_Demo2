from flask import Flask, request, jsonify
from flask_cors import CORS
from regression import multifidelity_regression, singlefidelity_regression

app = Flask(__name__)
CORS(app)

@app.route('/compute', methods=['POST'])
def compute():
    data = request.json
    mach = data.get('mach')
    alpha = data.get('alpha')
    beta = data.get('beta')
    solver = data.get('solver')
    print(f"Received request: mach={mach}, alpha={alpha}, beta={beta}, solver={solver}")

    if solver == "multi-fidelity":
        pressure_data, output_file = multifidelity_regression(mach, alpha, beta)
    elif solver == "single-fidelity":
        pressure_data, output_file = singlefidelity_regression(mach, alpha, beta)
    else:
        return jsonify({'status': 'error', 'output_file': None})

    return jsonify({'status': 'success', 'output_file': output_file})

if __name__ == '__main__':
    app.run(debug=True)
