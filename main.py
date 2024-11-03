

from paraview.web import venv
from paraview import simple
from vtkmodules.util.numpy_support import vtk_to_numpy
from paraview.servermanager import Fetch
from pathlib import Path
from trame.app import get_server
from trame.widgets import vuetify, paraview, client
from trame.ui.vuetify import SinglePageLayout
import requests  # Add this import

# Default view
DEFAULT_VEHICLE = "example.dat" # r"render_data\MF_prediction.dat"

# -----------------------------------------------------------------------------
# Trame setup
# -----------------------------------------------------------------------------

# server = get_server()
server = get_server(client_type="vue2")
state, ctrl = server.state, server.controller

# Preload paraview modules onto server
paraview.initialize(server)

# -----------------------------------------------------------------------------
# Global Variables
# -----------------------------------------------------------------------------

current_reader = None
view = None

# Initialize state variables
state.mach_number = 5.0
state.alpha = 0.0
state.beta = 0.0
state.solver_choice = "multi-fidelity"
state.solver_options = [
    {'text': 'Multi-fidelity', 'value': 'multi-fidelity'},
    {'text': 'Single-fidelity', 'value': 'single-fidelity'},
]

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

def setup_visualization(data_file):
    global current_reader, view
    # Delete previous data source if it exists
    if current_reader:
        simple.Delete(current_reader)
    current_reader = None

    # Force a pipeline reset to ensure no cache issues
    simple.Disconnect()  # Disconnect and reconnect to reset state
    simple.Connect()    

    # Load data file
    data_path = Path(data_file).resolve().absolute()
    try:
        reader = simple.OpenDataFile(str(data_path))
    except Exception as e:
        print(f"ERROR: Failed to load data file: {e}")
        return
    # reader = simple.OpenDataFile(str(data_path))
    reader.UpdatePipeline()
    current_reader = reader

    # Ensure 'PRESSURE' is a recognized field
    available_fields = reader.PointData.keys()
    if "PRESSURE" not in available_fields:
        print("ERROR: 'PRESSURE' field not found in data file.")
        return

    # Fetch the data to ensure accurate pressure value extraction
    fetched_data = Fetch(reader)

    # Multi-block data handling - ensure we capture all blocks
    pressure_values = []
    if fetched_data.IsA("vtkMultiBlockDataSet"):
        num_blocks = fetched_data.GetNumberOfBlocks()
        for i in range(num_blocks):
            block = fetched_data.GetBlock(i)
            if block and block.GetPointData().GetArray("PRESSURE"):
                pressure_array = block.GetPointData().GetArray("PRESSURE")
                pressure_values.extend(vtk_to_numpy(pressure_array))
    else:
        # Single dataset
        pressure_array = fetched_data.GetPointData().GetArray("PRESSURE")
        pressure_values = vtk_to_numpy(pressure_array)

    # Compute range of pressure values
    if pressure_values:
        min_pressure, max_pressure = min(pressure_values), max(pressure_values)
        print(f"Computed pressure range: min={min_pressure}, max={max_pressure}")
    else:
        print("ERROR: No pressure values found.")
        return

    # Set up visualization to display only the pressure field
    reader.DataArrayStatus = ["PRESSURE"]
    simple.Hide(reader)
    display = simple.Show(reader)
    display.SetRepresentationType("Surface")
    display.ColorArrayName = ["POINTS", "PRESSURE"]

    # Explicitly reset and apply the color map to avoid scaling issues
    color_map = simple.GetColorTransferFunction("PRESSURE")
    color_map.ApplyPreset("Cool to Warm", True)  # Apply a consistent color scheme
    color_map.RescaleTransferFunction(min_pressure, max_pressure)

    simple.LoadState("example.pvsm")  # Load state file for additional settings

    # Reset the camera to ensure full view and render the scene
    view = simple.GetActiveViewOrCreate("RenderView")
    view.ResetCamera()
    view.Update()
    view.MakeRenderWindowInteractor(True)
    simple.Render(view)

def on_compute(**kwargs):
    print("Called on_compute")
    global current_reader
    # Get user inputs
    mach = float(state.mach_number)
    alpha = float(state.alpha)
    beta = float(state.beta)
    solver = state.solver_choice

    # Send request to Flask server
    payload = {
        'mach': mach,
        'alpha': alpha,
        'beta': beta,
        'solver': solver
    }
    response = requests.post('http://127.0.0.1:5000/compute', json=payload)
    result = response.json()
    print(f"Received response: {result}")

    if result['status'] == 'success':
        output_file = result['output_file']
        print(f"Computation successful. Output file: {output_file}")

        # Update visualization with new data
        # load_data(data=output_file)
        setup_visualization(output_file)

        # Refresh the view
        ctrl.view_reset_camera()
        ctrl.view_update()
        state.flush()
    else:
        print("ERROR: Computation failed.")

ctrl.on_compute = on_compute

def load_data(**kwargs):
    args, _ = server.cli.parse_known_args()
    data_file = args.data or DEFAULT_VEHICLE

    # Set up visualization with initial data
    setup_visualization(data_file)

    # Define GUI layout
    with SinglePageLayout(server) as layout:
        layout.icon.click = ctrl.view_reset_camera
        layout.title.set_text("Hypersonic Vehicle Pressure Viewer")

        with layout.content:
            with vuetify.VContainer(fluid=True, classes="pa-0 fill-height"):
                with vuetify.VRow(classes="fill-height", justify="space-between"):
                    # First column is just empty space:
                    with vuetify.VCol(cols="1", classes="pl-3"):
                        pass
                    # Left column for inputs with left padding
                    with vuetify.VCol(cols="1", classes="pl-3"):  # Add padding-left here
                        vuetify.VTextField(
                            v_model=("mach_number", 5.0),
                            label="Mach Number (5-7)",
                            type="number",
                            step=0.1,
                        )
                        vuetify.VTextField(
                            v_model=("alpha", 0.0),
                            label="Angle of Attack (alpha)",
                            type="number",
                            step=0.1,
                        )
                        vuetify.VTextField(
                            v_model=("beta", 0.0),
                            label="Sideslip Angle (beta)",
                            type="number",
                            step=0.1,
                        )
                        vuetify.VSelect(
                            v_model=("solver_choice", "multi-fidelity"),
                            items=("solver_options",),  # Bind items to state.solver_options
                            label="Solver Choice",
                        )
                        vuetify.VBtn("Compute", click=ctrl.on_compute)
                    # Right column for visualization with full vertical height
                    with vuetify.VCol(cols="9", classes="d-flex flex-column fill-height"):
                        html_view = paraview.VtkRemoteView(view, style="flex: 1; height: 100%;")
                        ctrl.view_reset_camera = html_view.reset_camera
                        ctrl.view_update = html_view.update
                    # Last column is just empty space:
                    with vuetify.VCol(cols="1"):
                        pass

ctrl.on_server_ready.add(load_data)
# -----------------------------------------------------------------------------
# GUI
# -----------------------------------------------------------------------------

state.trame__title = "Hypersonic Vehicle Pressure Viewer"

with SinglePageLayout(server) as layout:
    layout.icon.click = ctrl.view_reset_camera
    layout.title.set_text("Hypersonic Vehicle Pressure Viewer")

    with layout.content:
        with vuetify.VContainer(fluid=True, classes="pa-0 fill-height"):
            client.Loading("Loading data")
# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    server.cli.add_argument("--data", help="Path to data file", dest="data")
    server.start()
