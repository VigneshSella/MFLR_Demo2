from paraview.web import venv
from paraview import simple
from vtkmodules.util.numpy_support import vtk_to_numpy
from paraview.servermanager import Fetch
from pathlib import Path
from trame.app import get_server
from trame.widgets import vuetify, paraview, client
from trame.ui.vuetify import SinglePageLayout

# -----------------------------------------------------------------------------
# Trame setup
# -----------------------------------------------------------------------------

server = get_server(client_type="vue2")
state, ctrl = server.state, server.controller

# Preload paraview modules onto server
paraview.initialize(server)

# -----------------------------------------------------------------------------
# ParaView code
# -----------------------------------------------------------------------------

def load_data(**kwargs):
    # CLI
    args, _ = server.cli.parse_known_args()
    data_file = args.data or "example.dat"

    # Load data file with reader-specific settings
    data_path = Path(data_file).resolve().absolute()
    reader = simple.OpenDataFile(str(data_path))
    reader.UpdatePipeline()  # Ensure the data is fully loaded before processing

    # Ensure 'PRESSURE' is a recognized field
    available_fields = reader.PointData.keys()
    print("Available fields:", available_fields)
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

    # HTML Layout for Web Display
    with SinglePageLayout(server) as layout:
        layout.icon.click = ctrl.view_reset_camera
        layout.title.set_text("Hypersonic Vehicle Pressure Viewer")

        with layout.content:
            with vuetify.VContainer(fluid=True, classes="pa-0 fill-height"):
                html_view = paraview.VtkRemoteView(view)
                ctrl.view_reset_camera = html_view.reset_camera
                ctrl.view_update = html_view.update

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
