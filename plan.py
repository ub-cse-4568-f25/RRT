from building_env import Coordinate
from building_env import get_buildings, create_deck, filter_buildings, path_to_coordinates, get_coordinate_transforms
from RRT import RRT
from shapely.ops import transform
import matplotlib.pyplot as plt


def get_building_polygon_projections(buildings, transfom_latlon_to_xy, altitude):
    buildings = filter_buildings(buildings, altitude)

    def project_geom(geom):
        return transform(transfom_latlon_to_xy.transform, geom)
    
    buildings_xy = [project_geom(geom) for geom in buildings["geometry"].tolist()]
    buildings_xy = [p.buffer(10.0) for p in buildings_xy]
    return buildings_xy

def plot_building_polygons_2D(polygons):
    plt.figure(figsize=(7,7))
    for poly in polygons:
        x, y = poly.exterior.xy
        plt.fill(x, y, color='gray', alpha=0.3)
    plt.scatter([sx, gx], [sy, gy], c=['g','r'])
    plt.axis('equal')
    plt.show()

def plot_path_2D(path_xy):
    if path_xy is not None:
        for poly in buildings_xy:
            x, y = poly.exterior.xy
            plt.fill(x, y, color='gray', alpha=0.4)
        plt.plot(path_xy[:,0], path_xy[:,1], 'r-', linewidth=2)
        plt.scatter([sx, gx], [sy, gy], c=['g','b'], marker='o')
        plt.axis('equal')
        plt.show()

def render_rrt_path(buildings, bbox, path_xy, transfom_xy_to_latlon, altitude):
    path_coords = path_to_coordinates(path_xy, transfom_xy_to_latlon, alt=altitude)
    deck_path = create_deck(bbox=bbox, buildings=buildings, path_list=[path_coords])
    deck_path.to_html("rrt_path.html", open_browser=True)

if __name__ == "__main__":

    # Convention is (west, south, east, north)
    bbox = (-73.98923, 40.74570, -73.98217, 40.75110)

    TEST_START_AND_END_COORDINATES = [
        [
            Coordinate(lat=40.7465, lon=-73.9882, alt=0.0, name="START 1"),
            Coordinate(lat=40.7495, lon=-73.9838, alt=0.0, name="END 1"),
        ],
        [
            Coordinate(lat=40.7478, lon=-73.9865, alt=0.0, name="START 2"),
            Coordinate(lat=40.7502, lon=-73.9842, alt=0.0, name="END 2"),
        ],
        [
            Coordinate(lat=40.7480, lon=-73.9875, alt=0.0, name="START 3"),
            Coordinate(lat=40.7487, lon=-73.9835, alt=0.0, name="END 3"),
        ],
        [
            Coordinate(lat=40.7455, lon=-73.9839, alt=0.0, name="START 4"),
            Coordinate(lat=40.7520, lon=-73.9892, alt=0.0, name="END 4"),
        ]
    ]

    # Fetch buildings from OSM
    buildings = get_buildings(bbox)
    deck = create_deck(bbox=bbox, buildings=buildings, path_list=TEST_START_AND_END_COORDINATES)
    deck.to_html("map.html", open_browser=True)


    transfom_latlon_to_xy, transfom_xy_to_latlon = get_coordinate_transforms(bbox)

    # Example for converting latlon to x,y
    w, s, e, n = bbox
    x_min, y_min = transfom_latlon_to_xy.transform(w, s)
    x_max, y_max = transfom_latlon_to_xy.transform(e, n)
    bounds = (x_min, x_max, y_min, y_max)


    # Start/goal from Pathfinder test set
    test_coordinates = TEST_START_AND_END_COORDINATES[0]
    sx, sy = transfom_latlon_to_xy.transform(test_coordinates[0].lon, test_coordinates[0].lat)
    gx, gy = transfom_latlon_to_xy.transform(test_coordinates[1].lon, test_coordinates[1].lat)

    # Use the buildings projected into XY
    altitude = 40.0

    path = None

    buildings_xy = get_building_polygon_projections(buildings, transfom_latlon_to_xy, altitude)

    plot_building_polygons_2D(buildings_xy)

    # Run RRT
    ##################################################################################
    # You can make changes here
    rrt = RRT(polygons=buildings_xy, bounds=bounds, link_thresh=3, n_itr=10000)
    path = rrt.get_path((sx, sy), (gx, gy))







    
    ##################################################################################


    plot_path_2D(path)
    render_rrt_path(buildings, bbox, path, transfom_xy_to_latlon, altitude)