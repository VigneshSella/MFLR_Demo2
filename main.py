

from paraview.web import venv
from paraview import simple
from vtkmodules.util.numpy_support import vtk_to_numpy
from paraview.servermanager import Fetch
from pathlib import Path
from trame.app import get_server
from trame.widgets import vuetify, paraview
from trame.ui.vuetify import SinglePageLayout
import requests  # Add this import

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

    # Load data file
    data_path = Path(data_file).resolve().absolute()
    reader = simple.OpenDataFile(str(data_path))
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

    # # Force the color bar to update with the rescaled range
    # color_bar = simple.GetScalarBar(color_map, simple.GetActiveView())
    # color_bar.Title = "Pressure (Pa)"
    # color_bar.ComponentTitle = ""
    # color_bar.Visibility = 1
    # simple.GetActiveView().Update()  # Update the view to apply all settings

    # Reset the camera to ensure full view and render the scene
    view = simple.GetActiveViewOrCreate("RenderView")
    view.ResetCamera()
    view.Update()
    view.MakeRenderWindowInteractor(True)
    simple.Render(view)

def on_compute(**kwargs):
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

    if result['status'] == 'success':
        output_file = result['output_file']

        # Update visualization with new data
        setup_visualization(output_file)

        # Refresh the view
        ctrl.view_update()
    else:
        print("ERROR: Computation failed.")

ctrl.on_compute = on_compute

def load_data(**kwargs):
    args, _ = server.cli.parse_known_args()
    data_file = args.data or "example.dat"

    # Set up visualization with initial data
    setup_visualization(data_file)

    # Define GUI layout
    with SinglePageLayout(server) as layout:
        layout.icon.click = ctrl.view_reset_camera
        layout.title.set_text("Hypersonic Vehicle Pressure Viewer")

        with layout.content:
            with vuetify.VContainer(fluid=True, classes="pa-0 fill-height"):
                with vuetify.VRow(classes="fill-height", justify="space-between"):
                    # Left column for inputs
                    with vuetify.VCol(cols="3"):
                        vuetify.VTextField(
                            v_model=("mach_number", 5.0),
                            label="Mach Number",
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


ctrl.on_server_ready.add(load_data)

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    server.cli.add_argument("--data", help="Path to data file", dest="data")
    server.start()
