class Configuration:
    _instance = None

    Boundary_Distance = 'boundary-distance'
    Min_Node_Distance = 'min-node-distance'
    Min_Node_Edge_Distance = 'min-node-edge-distance'
    Trajectory_Node_Distance = 'trajectory-node-distance'
    Buffer_Node_Distance = 'buffer-node-distance'
    Dim_X = 'dim-x'
    Dim_Y = 'dim-y'
    Dim_Table_X = 'dim-table-x'
    Dim_Table_Y = 'dim-table-y'
    Blocked_Space_Value = 'blocked-space-value'

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Configuration, cls).__new__(cls)
        return cls._instance

    def __init__(self, dim_x=None, dim_y=None):
        """
        Only one instance of this class is allowed. The constructor is called only once.
        """
        self.current_config = {
            # All distances should be integer values in cm.
            Configuration.Boundary_Distance: 0,  # Minimal distance between the boundary and the table configuration.
                                                  # 16 = A2NTS rotation radius / 2.
            Configuration.Min_Node_Distance: 32,  # Minimal distance between two nodes.
                                                  # 32 = A2NTS rotation radius.
            Configuration.Min_Node_Edge_Distance: 24,  # Minimal distance between a node and an edge.
                                                       # 24 = A2NTS rotation radius + A2NTS width / 2.
            Configuration.Trajectory_Node_Distance: 16,  # Distance between station boundary and station trajectory node.
                                                         # Distance has no physical meaning. Must be equal or larger than Boundary_Distance.
            Configuration.Buffer_Node_Distance: 32,  # Minimal distance between a buffer node and a station node.
            Configuration.Dim_Table_X: 100,  # Dimension of the tables in x direction (when angle is 0 degrees).
            Configuration.Dim_Table_Y: 50,  # Dimension of the tables in y direction (when angle is 0 degrees).
            Configuration.Dim_X: dim_x,  # Dimension of the usable area in x direction. Depends on the production layout.
            Configuration.Dim_Y: dim_y,  # Dimension of the usable area in y direction. Depends on the production layout.
            Configuration.Blocked_Space_Value: 0.55  # Value is used or the visualization.
        }

    def get(self, entry):
        return self.current_config[entry]

    def set(self, entry, value):
        if entry in self.current_config.keys():
            self.current_config[entry] = value
        else:
            raise ValueError(f"Invalid entry: {entry}")
