# Copyright (C) 2006 Anders Logg
# Licensed under the GNU LGPL Version 2.1
#
# Modified by Garth N. Wells (gmsh function)
# Modified by Alexander H. Jarosch (gmsh fix)
# Modified by Angelo Simone (Gmsh and Medit fix)
# Modified by Andy R. Terrel (gmsh fix and triangle function)
# Modified by Magnus Vikstrom (metis and scotch function)
# Modified by Bartosz Sawicki (diffpack function)
# Modified by Gideon Simpson (Exodus II function)
# Modified by Arve Knudsen (make into module, abaqus support)
# Modified by Kent-Andre Mardal (Star-CD function)
# Modified by Nuno Lopes (fix for emc2 mesh format (medit version 0))
""" Module for converting various mesh formats.
"""

import getopt
import sys
from dolfin_utils.commands import getoutput
import re
import warnings
import os.path

def format_from_suffix(suffix):
    "Return format for given suffix"
    if suffix == "xml":
        return "xml"
    elif suffix == "mesh":
        return "mesh"
    elif suffix == "gmsh":
        return "gmsh"
    elif suffix == "msh":
        return "gmsh"
    elif suffix == "gra":
        return "metis"
    elif suffix == "grf":
        return "scotch"
    elif suffix == "grid":
        return "diffpack"
    elif suffix == "inp":
        return "abaqus"
    elif suffix == "ncdf":
        return "NetCDF"
    elif suffix =="exo":
        return "ExodusII"
    elif suffix =="e":
        return "ExodusII"
    elif suffix == "vrt" or suffix == "cel":
        return "StarCD"
    else:
        _error("Sorry, unknown suffix %s." % suffix)

def mesh2xml(ifilename, ofilename):
    """Convert between .mesh and .xml, parser implemented as a
    state machine:

        0 = read 'Dimension'
        1 = read dimension
        2 = read 'Vertices'
        3 = read number of vertices
        4 = read next vertex
        5 = read 'Triangles' or 'Tetrahedra'
        6 = read number of cells
        7 = read next cell
        8 = done

    """

    print "Converting from Medit format (.mesh) to DOLFIN XML format"

    # Open files
    ifile = open(ifilename, "r")
    ofile = open(ofilename, "w")

    # Scan file for cell type
    cell_type = None
    dim = 0
    while 1:

        # Read next line
        line = ifile.readline()
        if not line: break

        # Remove newline
        if line[-1] == "\n":
            line = line[:-1]

        # Read dimension
        if  line == "Dimension" or line == " Dimension":
            line = ifile.readline()
            num_dims = int(line)
            if num_dims == 2:
                cell_type = "triangle"
                dim = 2
            elif num_dims == 3:
                cell_type = "tetrahedron"
                dim = 3
            break

    # Check that we got the cell type
    if cell_type == None:
        _error("Unable to find cell type.")

    # Step to beginning of file
    ifile.seek(0)

    # Write header
    write_header_mesh(ofile, cell_type, dim)

    # Current state
    state = 0

    # Write data
    num_vertices_read = 0
    num_cells_read = 0

    while 1:

        # Read next line
        line = ifile.readline()
        if not line: break

        # Skip comments
        if line[0] == '#':
            continue

        # Remove newline
        if line[-1] == "\n":
            line = line[:-1]

        if state == 0:
            if line == "Dimension" or line == " Dimension":
                state += 1
        elif state == 1:
            num_dims = int(line)
            state +=1
        elif state == 2:
            if line == "Vertices" or line == " Vertices":
                state += 1
        elif state == 3:
            num_vertices = int(line)
            write_header_vertices(ofile, num_vertices)
            state +=1
        elif state == 4:
            if num_dims == 2:
                (x, y, tmp) = line.split()
                x = float(x)
                y = float(y)
                z = 0.0
            elif num_dims == 3:
                (x, y, z, tmp) = line.split()
                x = float(x)
                y = float(y)
                z = float(z)
            write_vertex(ofile, num_vertices_read, x, y, z)
            num_vertices_read +=1
            if num_vertices == num_vertices_read:
                write_footer_vertices(ofile)
                state += 1
        elif state == 5:
            if (line == "Triangles"  or line == " Triangles") and num_dims == 2:
                state += 1
            if line == "Tetrahedra" and num_dims == 3:
                state += 1
        elif state == 6:
            num_cells = int(line)
            write_header_cells(ofile, num_cells)
            state +=1
        elif state == 7:
            if num_dims == 2:
                (n0, n1, n2, tmp) = line.split()
                n0 = int(n0) - 1
                n1 = int(n1) - 1
                n2 = int(n2) - 1
                write_cell_triangle(ofile, num_cells_read, n0, n1, n2)
            elif num_dims == 3:
                (n0, n1, n2, n3, tmp) = line.split()
                n0 = int(n0) - 1
                n1 = int(n1) - 1
                n2 = int(n2) - 1
                n3 = int(n3) - 1
                write_cell_tetrahedron(ofile, num_cells_read, n0, n1, n2, n3)
            num_cells_read +=1
            if num_cells == num_cells_read:
                write_footer_cells(ofile)
                state += 1
        elif state == 8:
            break

    # Check that we got all data
    if state == 8:
        print "Conversion done"
    else:
        _error("Missing data, unable to convert")

    # Write footer
    write_footer_mesh(ofile)

    # Close files
    ifile.close()
    ofile.close()

def gmsh2xml(ifilename, handler):
    """Convert between .gmsh v2.0 format (http://www.geuz.org/gmsh/) and .xml,
    parser implemented as a state machine:

        0 = read 'MeshFormat'
        1 = read  mesh format data
        2 = read 'EndMeshFormat'
        3 = read 'Nodes'
        4 = read  number of vertices
        5 = read  vertices
        6 = read 'EndNodes'
        7 = read 'Elements'
        8 = read  number of cells
        9 = read  cells
        10 = done

    """

    print "Converting from Gmsh format (.msh, .gmsh) to DOLFIN XML format"

    # Open files
    ifile = open(ifilename, "r")

    # Scan file for cell type
    cell_type = None
    dim = 0
    line = ifile.readline()
    while line:

        # Remove newline
        if line[-1] == "\n":
            line = line[:-1]

        # Read dimension
        if line.find("$Elements") == 0:

            line = ifile.readline()
            num_cells  = int(line)
            num_cells_counted = 0
            if num_cells == 0:
                _error("No cells found in gmsh file.")
            line = ifile.readline()

            # Now iterate through elements to find largest dimension.  Gmsh
            # format might include elements of lower dimensions in the element list.
            # We also need to count number of elements of correct dimensions.
            # Also determine which vertices are not used.
            dim_2_count = 0
            dim_3_count = 0
            vertices_2_used = []
            # Array used to store gmsh tags for 2D (type 2/triangular) elements
            tags_2 = []
            # Array used to store gmsh tags for 3D (type 4/tet) elements
            tags_3 = []
            vertices_3_used = []
            while line.find("$EndElements") == -1:
                element = line.split()
                elem_type = int(element[1])
                num_tags = int(element[2])
                if elem_type == 2:
                    if dim < 2:
                        cell_type = "triangle"
                        dim = 2
                    node_num_list = [int(node) for node in element[3 + num_tags:]]
                    vertices_2_used.extend(node_num_list)
                    if num_tags > 0:
                        tags_2.append(tuple(int(tag) for tag in element[3:3+num_tags]))
                    dim_2_count += 1
                elif elem_type == 4:
                    if dim < 3:
                        cell_type = "tetrahedron"
                        dim = 3
                        vertices_2_used = None
                    node_num_list = [int(node) for node in element[3 + num_tags:]]
                    vertices_3_used.extend(node_num_list)
                    if num_tags > 0:
                        tags_3.append(tuple(int(tag) for tag in element[3:3+num_tags]))
                    dim_3_count += 1
                line = ifile.readline()
        else:
            # Read next line
            line = ifile.readline()

    # Check that we got the cell type and set num_cells_counted
    if cell_type == None:
        _error("Unable to find cell type.")
    if dim == 3:
        num_cells_counted = dim_3_count
        vertex_set = set(vertices_3_used)
        vertices_3_used = None
    elif dim == 2:
        num_cells_counted = dim_2_count
        vertex_set = set(vertices_2_used)
        vertices_2_used = None

    vertex_dict = {}
    for n,v in enumerate(vertex_set):
        vertex_dict[v] = n

    # Step to beginning of file
    ifile.seek(0)
    
    # Set mesh type
    handler.set_mesh_type(cell_type, dim)

    # Initialise node list (gmsh does not export all vertexes in order)
    nodelist = {}

    # Current state
    state = 0

    # Write data
    num_vertices_read = 0
    num_cells_read = 0

    while state != 10:

        # Read next line
        line = ifile.readline()
        if not line: break

        # Skip comments
        if line[0] == '#':
            continue

        # Remove newline
        if line[-1] == "\n":
            line = line[:-1]

        if state == 0:
            if line == "$MeshFormat":
                state = 1
        elif state == 1:
            (version, file_type, data_size) = line.split()
            state = 2
        elif state == 2:
            if line == "$EndMeshFormat":
                state = 3
        elif state == 3:
            if line == "$Nodes":
                state = 4
        elif state == 4:
            num_vertices = len(vertex_dict)
            handler.start_vertices(num_vertices)
            state = 5
        elif state == 5:
            (node_no, x, y, z) = line.split()
            if vertex_dict.has_key(int(node_no)):
                node_no = vertex_dict[int(node_no)]
            else:
                continue
            nodelist[int(node_no)] = num_vertices_read
            handler.add_vertex(num_vertices_read, [x, y, z])
            num_vertices_read +=1

            if num_vertices == num_vertices_read:
                handler.end_vertices()
                state = 6
        elif state == 6:
            if line == "$EndNodes":
                state = 7
        elif state == 7:
            if line == "$Elements":
                state = 8
        elif state == 8:
            handler.start_cells(num_cells_counted)
            state = 9
        elif state == 9:
            element = line.split()
            elem_type = int(element[1])
            num_tags  = int(element[2])
            if elem_type == 2 and dim == 2:
                node_num_list = [vertex_dict[int(node)] for node in element[3 + num_tags:]]
                for node in node_num_list:
                    if not node in nodelist:
                        _error("Vertex %d of triangle %d not previously defined." %
                              (node, num_cells_read))
                handler.add_cell(num_cells_read, node_num_list)
                num_cells_read +=1
            elif elem_type == 4 and dim == 3:
                node_num_list = [vertex_dict[int(node)] for node in element[3 + num_tags:]]
                for node in node_num_list:
                    if not node in nodelist:
                        _error("Vertex %d of tetrahedron %d not previously defined." %
                              (node, num_cells_read))
                handler.add_cell(num_cells_read, node_num_list)
                num_cells_read +=1

            if num_cells_counted == num_cells_read:
                handler.end_cells()
                state = 10
        elif state == 10:
            break

    # Write mesh function based on the Physical Regions defined by
    # gmsh, but only if they are not all zero. All zero physical
    # regions indicate that no physical regions were defined.
    if dim == 2:
        tags = tags_2
    elif dim == 3:
        tags = tags_3
    else:
        _error("Gmsh tags not supported for dimension %i. Probably a bug" % dim)

    physical_regions = tuple(tag[0] for tag in tags)
    if not all(tag == 0 for tag in tags):
        handler.start_meshfunction("physical_region", dim, num_cells)
        for i, physical_region in enumerate(physical_regions):
            handler.add_entity_meshfunction(i, physical_region)
        handler.end_meshfunction()
    
    # Check that we got all data
    if state == 10:
        print "Conversion done"
    else:
       _error("Missing data, unable to convert \n\ Did you use version 2.0 of the gmsh file format?")

    # Close files
    ifile.close()

def triangle2xml(ifilename, ofilename):
    """Convert between triangle format (http://www.cs.cmu.edu/~quake/triangle.html) and .xml.  The
    given ifilename should be the prefix for the corresponding .node, and .ele files.
    """

    def get_next_line (fp):
        """Helper function for skipping comments and blank lines"""
        line = fp.readline()
        if line == '':
            _error("Hit end of file prematurely.")
        line = line.strip()
        if not (line.startswith('#') or line == ''):
            return line
        return get_next_line(fp)


    print "Converting from Triangle format {.node, .ele} to DOLFIN XML format"

    # Open files
    node_file = open(ifilename+".node", "r")
    ele_file =  open(ifilename+".ele", "r")
    ofile = open(ofilename, "w")

    # Read all the nodes
    nodes = {}
    num_nodes, dim, attr, bound = map(int, get_next_line(node_file).split())
    while len(nodes) < num_nodes:
        node, x, y = get_next_line(node_file).split()[:3]
        nodes[int(node)] = (float(x), float(y))

    # Read all the triangles
    tris = {}
    num_tris, n_per_tri, attrs = map(int, get_next_line(ele_file).split())
    while len(tris) < num_tris:
        tri, n1, n2, n3 = map(int, get_next_line(ele_file).split()[:4])
        tris[tri] = (n1, n2, n3)

    # Write everything out
    write_header_mesh(ofile, "triangle", 2)
    write_header_vertices(ofile, num_nodes)
    node_off = 0 if nodes.has_key(0) else -1
    for node, node_t in nodes.iteritems():
        write_vertex(ofile, node+node_off, node_t[0], node_t[1], 0.0)
    write_footer_vertices(ofile)
    write_header_cells(ofile, num_tris)
    tri_off = 0 if tris.has_key(0) else -1
    for tri, tri_t in tris.iteritems():
        write_cell_triangle(ofile, tri+tri_off, tri_t[0] + node_off,
                            tri_t[1] + node_off, tri_t[2] + node_off)
    write_footer_cells(ofile)
    write_footer_mesh(ofile)

    # Close files
    node_file.close()
    ele_file.close()
    ofile.close()


def xml_old2xml(ifilename, ofilename):
    "Convert from old DOLFIN XML format to new."

    print "Converting from old (pre DOLFIN 0.6.2) to new DOLFIN XML format..."

    # Open files
    ifile = open(ifilename, "r")
    ofile = open(ofilename, "w")

    # Scan file for cell type (assuming there is just one)
    cell_type = None
    dim = 0
    while 1:

        # Read next line
        line = ifile.readline()
        if not line: break

        # Read dimension
        if "<triangle" in line:
            cell_type = "triangle"
            dim = 2
            break
        elif "<tetrahedron" in line:
            cell_type = "tetrahedron"
            dim = 3
            break

    # Step to beginning of file
    ifile.seek(0)

    # Read lines and make changes
    while 1:

        # Read next line
        line = ifile.readline()
        if not line: break

        # Modify line
        if "xmlns" in line:
            line = "<dolfin xmlns:dolfin=\"http://www.fenicsproject.org\">\n"
        if "<mesh>" in line:
            line = "  <mesh celltype=\"%s\" dim=\"%d\">\n" % (cell_type, dim)
        if dim == 2 and " z=\"0.0\"" in line:
            line = line.replace(" z=\"0.0\"", "")
        if " name=" in line:
            line = line.replace(" name=", " index=")
        if " name =" in line:
            line = line.replace(" name =", " index=")
        if "n0" in line:
            line = line.replace("n0", "v0")
        if "n1" in line:
            line = line.replace("n1", "v1")
        if "n2" in line:
            line = line.replace("n2", "v2")
        if "n3" in line:
            line = line.replace("n3", "v3")

        # Write line
        ofile.write(line)

    # Close files
    ifile.close();
    ofile.close();
    print "Conversion done"

def metis_graph2graph_xml(ifilename, ofilename):
    "Convert from Metis graph format to DOLFIN Graph XML."

    print "Converting from Metis graph format to DOLFIN Graph XML."

    # Open files
    ifile = open(ifilename, "r")
    ofile = open(ofilename, "w")

    # Read number of vertices and edges
    line = ifile.readline()
    if not line:
       _error("Empty file")

    (num_vertices, num_edges) = line.split()

    write_header_graph(ofile, "directed")
    write_header_vertices(ofile, int(num_vertices))

    for i in range(int(num_vertices)):
        line = ifile.readline()
        edges = line.split()
        write_graph_vertex(ofile, i, len(edges))

    write_footer_vertices(ofile)
    write_header_edges(ofile, 2*int(num_edges))

    # Step to beginning of file and skip header info
    ifile.seek(0)
    ifile.readline()
    for i in range(int(num_vertices)):
        print "vertex %g", i
        line = ifile.readline()
        edges = line.split()
        for e in edges:
            write_graph_edge(ofile, i, int(e))

    write_footer_edges(ofile)
    write_footer_graph(ofile)

    # Close files
    ifile.close();
    ofile.close();

def scotch_graph2graph_xml(ifilename, ofilename):
    "Convert from Scotch graph format to DOLFIN Graph XML."

    print "Converting from Scotch graph format to DOLFIN Graph XML."

    # Open files
    ifile = open(ifilename, "r")
    ofile = open(ofilename, "w")

    # Skip graph file version number
    ifile.readline()

    # Read number of vertices and edges
    line = ifile.readline()
    if not line:
       _error("Empty file")

    (num_vertices, num_edges) = line.split()

    # Read start index and numeric flag
    # Start index is 0 or 1 (C/Fortran)
    # Numeric flag is 3 bits where bit 1 enables vertex labels
    # bit 2 enables edge weights and bit 3 enables vertex weights

    line = ifile.readline()
    (start_index, numeric_flag) = line.split()

    # Handling not implented
    if not numeric_flag == "000":
       _error("Handling of scotch vertex labels, edge- and vertex weights not implemented")

    write_header_graph(ofile, "undirected")
    write_header_vertices(ofile, int(num_vertices))

    # Read vertices and edges, first number gives number of edges from this vertex (not used)
    for i in range(int(num_vertices)):
        line = ifile.readline()
        edges = line.split()
        write_graph_vertex(ofile, i, len(edges)-1)

    write_footer_vertices(ofile)
    write_header_edges(ofile, int(num_edges))


    # Step to beginning of file and skip header info
    ifile.seek(0)
    ifile.readline()
    ifile.readline()
    ifile.readline()
    for i in range(int(num_vertices)):
        line = ifile.readline()

        edges = line.split()
        for j in range(1, len(edges)):
            write_graph_edge(ofile, i, int(edges[j]))

    write_footer_edges(ofile)
    write_footer_graph(ofile)

    # Close files
    ifile.close();
    ofile.close();

def write_header_meshfunction(ofile, dimensions, size):
    header = """<?xml version="1.0" encoding="UTF-8"?>
<dolfin xmlns:dolfin="http://www.fenics.org/dolfin/">
  <meshfunction type="uint" dim="%d" size="%d">
""" % (dimensions, size)
    ofile.write(header)

def write_entity_meshfunction(ofile, index, value):
    ofile.write("""    <entity index=\"%d\" value=\"%d\"/>
""" % (index, value))

def write_footer_meshfunction(ofile):
    ofile.write("""  </meshfunction>
</dolfin>""")

def diffpack2xml(ifilename, ofilename):
    "Convert from Diffpack tetrahedral grid format to DOLFIN XML."

    print diffpack2xml.__doc__

    # Format strings for MeshFunction XML files
    meshfunction_header = """\
<?xml version="1.0" encoding="UTF-8"?>\n
<dolfin xmlns:dolfin="http://www.fenics.org/dolfin/">
  <meshfunction type="uint" dim="%d" size="%d">\n"""
    meshfunction_entity = "    <entity index=\"%d\" value=\"%d\"/>\n"
    meshfunction_footer = "  </meshfunction>\n</dolfin>"

    # Open files
    ifile = open(ifilename, "r")
    ofile = open(ofilename, "w")
    ofile_mat = open(ofilename.split(".")[0]+"_mat.xml", "w")
    ofile_bi = open(ofilename.split(".")[0]+"_bi.xml", "w")

    # Read and analyze header
    while 1:
        line = ifile.readline()
        if not line:
           _error("Empty file")
        if line[0] == "#":
            break
        if re.search(r"Number of elements", line):
	    num_cells = int(re.match(r".*\s(\d+).*", line).group(1))
        if re.search(r"Number of nodes", line):
	    num_vertices = int(re.match(r".*\s(\d+).*", line).group(1))

    write_header_mesh(ofile, "tetrahedron", 3)
    write_header_vertices(ofile, num_vertices)
    ofile_bi.write(meshfunction_header % (0, num_vertices))
    ofile_mat.write(meshfunction_header % (3, num_cells))

    # Read & write vertices
    # Note that only first boundary indicator is rewriten into XML
    for i in range(num_vertices):
        line = ifile.readline()
        m = re.match(r"^.*\(\s*(.*)\s*\).*\](.*)$", line)
        x = re.split("[\s,]+", m.group(1))
        write_vertex(ofile, i, x[0], x[1], x[2])
        tmp = m.group(2).split()
        if len(tmp) > 0:
            bi = int(tmp[0])
        else:
            bi = 0
        ofile_bi.write(meshfunction_entity % (i, bi))

    write_footer_vertices(ofile)
    write_header_cells(ofile, num_cells)

    # Ignore comment lines
    while 1:
        line = ifile.readline()
        if not line:
           _error("Empty file")
        if line[0] == "#":
            break

    # Read & write cells
    for i in range(int(num_cells)):
        line = ifile.readline()
        v = line.split();
        if v[1] != "ElmT4n3D":
           _error("Only tetrahedral elements (ElmT4n3D) are implemented.")
        write_cell_tetrahedron(ofile, i, int(v[3])-1, int(v[4])-1, int(v[5])-1, int(v[6])-1)
        ofile_mat.write(meshfunction_entity % (i, int(v[2])))

    write_footer_cells(ofile)
    write_footer_mesh(ofile)
    ofile_bi.write(meshfunction_footer)
    ofile_mat.write(meshfunction_footer)

    # Close files
    ifile.close()
    ofile.close()
    ofile_mat.close()
    ofile_bi.close()

class ParseError(Exception):
    """ Error encountered in source file.
    """

class DataHandler(object):
    """ Baseclass for handlers of mesh data.

    The actual handling of mesh data encountered in the source file is
    delegated to a polymorfic object. Typically, the delegate will write the
    data to XML.
    @ivar _state: the state which the handler is in, one of State_*.
    @ivar _cell_type: cell type in mesh. One of CellType_*.
    @ivar _dim: mesh dimensions.
    """
    State_Invalid, State_Init, State_Vertices, State_Cells, State_MeshFunction = range(5)
    CellType_Tetrahedron, CellType_Triangle = range(2)

    def __init__(self):
        self._state = self.State_Invalid

    def set_mesh_type(self, cell_type, dim):
        assert self._state == self.State_Invalid
        self._state = self.State_Init
        if cell_type == "tetrahedron":
            self._cell_type = self.CellType_Tetrahedron
        elif cell_type == "triangle":
            self._cell_type = self.CellType_Triangle
        self._dim = dim

    def start_vertices(self, num_vertices):
        assert self._state == self.State_Init
        self._state = self.State_Vertices

    def add_vertex(self, vertex, coords):
        assert self._state == self.State_Vertices

    def end_vertices(self):
        assert self._state == self.State_Vertices
        self._state = self.State_Init

    def start_cells(self, num_cells):
        assert self._state == self.State_Init
        self._state = self.State_Cells

    def add_cell(self, cell, nodes):
        assert self._state == self.State_Cells

    def end_cells(self):
        assert self._state == self.State_Cells
        self._state = self.State_Init

    def start_meshfunction(self, name, dim, size):
        assert self._state == self.State_Init
        self._state = self.State_MeshFunction

    def add_entity_meshfunction(self, index, value):
        assert self._state == self.State_MeshFunction

    def end_meshfunction(self):
        assert self._state == self.State_MeshFunction
        self._state = self.State_Init

    def warn(self, msg):
        """ Issue warning during parse.
        """
        warnings.warn(msg)

    def error(self, msg):
        """ Raise error during parse.

        This method is expected to raise ParseError.
        """
        raise ParseError(msg)

    def close(self):
        self._state = self.State_Invalid

class XmlHandler(DataHandler):
    """ Data handler class which writes to Dolfin XML.
    """
    def __init__(self, ofilename):
        DataHandler.__init__(self)
        self._ofilename = ofilename
        self.__ofile = file(ofilename, "wb")
        self.__ofile_meshfunc = None

    def set_mesh_type(self, cell_type, dim):
        DataHandler.set_mesh_type(self, cell_type, dim)
        write_header_mesh(self.__ofile, cell_type, dim)

    def start_vertices(self, num_vertices):
        DataHandler.start_vertices(self, num_vertices)
        write_header_vertices(self.__ofile, num_vertices)

    def add_vertex(self, vertex, coords):
        DataHandler.add_vertex(self, vertex, coords)
        write_vertex(self.__ofile, vertex, *coords)

    def end_vertices(self):
        DataHandler.end_vertices(self)
        write_footer_vertices(self.__ofile)

    def start_cells(self, num_cells):
        DataHandler.start_cells(self, num_cells)
        write_header_cells(self.__ofile, num_cells)

    def add_cell(self, cell, nodes):
        DataHandler.add_cell(self, cell, nodes)
        if self._cell_type == self.CellType_Tetrahedron:
            func = write_cell_tetrahedron
        func(self.__ofile, cell, *nodes)

    def end_cells(self):
        DataHandler.end_cells(self)
        write_footer_cells(self.__ofile)

    def start_meshfunction(self, name, dim, size):
        DataHandler.start_meshfunction(self, name, dim, size)
        fname = os.path.splitext(self.__ofile.name)[0]
        self.__ofile_meshfunc = file("%s_%s.xml" % (fname, name), "wb")
        write_header_meshfunction(self.__ofile_meshfunc, dim, size)

    def add_entity_meshfunction(self, index, value):
        DataHandler.add_entity_meshfunction(self, index, value)
        write_entity_meshfunction(self.__ofile_meshfunc, index, value)

    def end_meshfunction(self):
        DataHandler.end_meshfunction(self)
        write_footer_meshfunction(self.__ofile_meshfunc)
        self.__ofile_meshfunc.close()
        self.__ofile_meshfunc = None

    def close(self):
        DataHandler.close(self)
        if self.__ofile.closed:
            return
        write_footer_mesh(self.__ofile)
        self.__ofile.close()
        if self.__ofile_meshfunc is not None:
            self.__ofile_meshfunc.close()

def _abaqus(ifilename, handler):
    """ Convert from Abaqus.

    The Abaqus format first defines a node block, then there should be a number
    of elements containing these nodes.
    """
    params = False
    ifile = file(ifilename, "rb")
    handler.set_mesh_type("tetrahedron", 3)

    # Read definitions

    def read_params(params_spec, pnames, lineno):
        params = {}
        for p in params_spec:
            m = re.match(r"(.+)=(.+)", p)
            if m is not None:
                pname, val = m.groups()
            else:
                handler.warn("Invalid parameter syntax on line %d: %s" % (lineno, p))
                continue
            for pn in pnames:
                if pn == pname:
                    params[pn] = val
                    break

        return params

    nodes = {}
    elems = {}
    eid2elset = {}
    material2elsetids = {}
    materials = []
    re_sect = re.compile(r"\*([^,]+)(?:,(.*))?")
    re_node = re.compile(r"(\d+),\s*(.+),\s*(.+),\s*(.+)")
    re_tetra = re.compile(r"(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)")
    sect = None
    for lineno, l in enumerate(ifile):
        l = l.strip().lower()
        m = re_sect.match(l)
        if m is not None:
            sect, params_str = m.groups()
            params_spec = ([s.strip() for s in params_str.split(",")] if params_str
                    else [])

            if sect == "element":
                pnames = ("type", "elset")
                params = read_params(params_spec, pnames, lineno)
                if "type" not in params:
                   handler.error("Element on line %d doesn't declare TYPE" %
                            (lineno,))
                tp, elset = params["type"], params.get("elset")
                if tp not in ("c3d4", "dc3d4"):
                    handler.warn("Unsupported element type '%s' on line %d" % (tp, lineno))
                    supported_elem = False
                else:
                    supported_elem = True
            elif sect == "solid section":
                pnames = ("material", "elset")
                params = read_params(params_spec, pnames, lineno)
                for pname in pnames:
                    if pname not in params:
                       handler.error("Solid section on line %d doesn't "
                                "declare %s" % (lineno, pname.upper()))
                matname = params["material"]
                material2elsetids.setdefault(matname, []).append(params["elset"])
            elif sect == "material":
                name = read_params(params_spec, ["name"], lineno)["name"]
                materials.append(name)
            # We've read the section's heading, continue to next line
            continue

        # Read section entry

        if sect == "node":
            # Read node definition
            m = re_node.match(l)
            if m is None:
                handler.warn("Node on line %d is on unsupported format" % (lineno,))
                continue
            idx, c0, c1, c2 = m.groups()
            try: coords = [float(c) for c in (c0, c1, c2)]
            except ValueError:
                handler.warn("Node on line %d contains non-numeric coordinates"
                        % (lineno,))
                continue
            nodes[int(idx)] = coords
        elif sect == "element":
            if not supported_elem:
                continue
            m = re_tetra.match(l)
            if m is None:
                handler.error("Node on line %d badly specified (expected 3 "
                        "coordinates)" % (lineno,))
            idx, n0, n1, n2, n3 = [int(x) for x in m.groups()]
            elems[idx] = (tp, n0, n1, n2, n3)
            eid2elset.setdefault(elset, set()).add(idx)

    ifile.close()

    # Note that vertices/cells must be consecutively numbered, which isn't
    # necessarily the case in Abaqus. Therefore we enumerate and translate
    # original IDs to sequence indexes.

    handler.start_vertices(len(nodes))
    nodeids = nodes.keys()
    nodeids.sort()
    for idx, nid in enumerate(nodeids):
        handler.add_vertex(idx, nodes[nid])
    handler.end_vertices()

    handler.start_cells(len(elems))
    elemids = elems.keys()
    elemids.sort()
    for idx, eid in enumerate(elemids):
        elem = elems[eid]
        tp = elem[0]
        elemnodes = []
        for nid in elem[1:]:
            try: elemnodes.append(nodeids.index(nid))
            except ValueError:
                handler.error("Element %s references non-existent node %s" % (eid, nid))
        handler.add_cell(idx, elemnodes)
    handler.end_cells()

    # Define the material function for the cells

    num_entities = 0
    for matname, elsetids in material2elsetids.items():
        if matname not in materials:
            handler.error("Unknown material %s referred to for element sets %s" %
                    (matname, ", ".join(elsetids)))
        num_entities += len(elsetids)
    handler.start_meshfunction("material", 3, num_entities)
    # Each material is associated with a number of element sets
    for i, matname in enumerate(materials):
        try: elsetids = material2elsetids[matname]
        except KeyError:
            # No elements for this material
            continue
        # For each element set associated with this material
        elsets = []
        for eid in elsetids:
            try: elsets.append(eid2elset[eid])
            except KeyError:
                handler.error("Material '%s' is assigned to undefined element "
                        "set '%s'" % (matname, eid))
        for elset in elsets:
            for elemid in elset:
                handler.add_entity_meshfunction(elemids.index(elemid), i)
    handler.end_meshfunction()

def netcdf2xml(ifilename,ofilename):
    "Convert from NetCDF format to DOLFIN XML."

    print "Converting from NetCDF format (.ncdf) to DOLFIN XML format"

    # Open files
    ifile = open(ifilename, "r")
    ofile = open(ofilename, "w")


    cell_type = None
    dim = 0

    # Scan file for dimension, number of nodes, number of elements
    while 1:
        line = ifile.readline()
        if not line:
            error("Empty file")
        if re.search(r"num_dim.*=", line):
            dim = int(re.match(".*\s=\s(\d+)\s;",line).group(1))
        if re.search(r"num_nodes.*=", line):
            num_vertices = int(re.match(".*\s=\s(\d+)\s;",line).group(1))
        if re.search(r"num_elem.*=", line):
            num_cells = int(re.match(".*\s=\s(\d+)\s;",line).group(1))
        if re.search(r"connect1 =",line):
            break

    num_dims=dim

    # Set cell type
    if dim == 2:
        cell_type ="triangle"
    if dim == 3:
        cell_type ="tetrahedron"

    # Check that we got the cell type
    if cell_type == None:
        error("Unable to find cell type.")

    # Write header
    write_header_mesh(ofile, cell_type, dim)
    write_header_cells(ofile, num_cells)
    num_cells_read = 0

    # Read and write cells
    while 1:
        # Read next line
        line = ifile.readline()
        if not line:
            break
        connect=re.split("[,;]",line)
        if num_dims == 2:
            n0 = int(connect[0])-1
            n1 = int(connect[1])-1
            n2 = int(connect[2])-1
            write_cell_triangle(ofile, num_cells_read, n0, n1, n2)
        elif num_dims == 3:
            n0 = int(connect[0])-1
            n1 = int(connect[1])-1
            n2 = int(connect[2])-1
            n3 = int(connect[3])-1
            write_cell_tetrahedron(ofile, num_cells_read, n0, n1, n2, n3)
        num_cells_read +=1
        if num_cells == num_cells_read:
           write_footer_cells(ofile)
           write_header_vertices(ofile, num_vertices)
           break

    num_vertices_read = 0
    coords = [[],[],[]]
    coord = -1

    while 1:
        line = ifile.readline()
        if not line:
            error("Missing data")
        if re.search(r"coord =",line):
            break

    # Read vertices
    while 1:
        line = ifile.readline()
#        print line
        if not line:
            break
        if re.search(r"\A\s\s\S+,",line):
#            print line
            coord+=1
            print "Found x_"+str(coord)+" coordinates"
        coords[coord] += line.split()
        if re.search(r";",line):
            break

    # Write vertices
    for i in range(num_vertices):
        if num_dims == 2:
            x = float(re.split(",",coords[0].pop(0))[0])
            y = float(re.split(",",coords[1].pop(0))[0])
            z = 0
        if num_dims == 3:
            x = float(re.split(",",coords[0].pop(0))[0])
            y = float(re.split(",",coords[1].pop(0))[0])
            z = float(re.split(",",coords[2].pop(0))[0])
        write_vertex(ofile, i, x, y, z)


    # Write footer
    write_footer_vertices(ofile)
    write_footer_mesh(ofile)

    # Close files
    ifile.close()
    ofile.close()

def exodus2xml(ifilename,ofilename):
    "Convert from Exodus II format to DOLFIN XML."

    print "Converting from Exodus II format to NetCDF format"

    name = ifilename.split(".")[0]
    netcdffilename = name +".ncdf"
    os.system('ncdump '+ifilename + ' > '+netcdffilename)
    netcdf2xml(netcdffilename,ofilename)

# Write mesh header
def write_header_mesh(ofile, cell_type, dim):
    ofile.write("""\
<?xml version=\"1.0\" encoding=\"UTF-8\"?>

<dolfin xmlns:dolfin=\"http://www.fenics.org/dolfin/\">
  <mesh celltype="%s" dim="%d">
""" % (cell_type, dim))

# Write graph header
def write_header_graph(ofile, graph_type):
    ofile.write("""\
<?xml version=\"1.0\" encoding=\"UTF-8\"?>

<dolfin xmlns:dolfin=\"http://www.fenics.org/dolfin/\">
  <graph type="%s">
""" % (graph_type))

# Write mesh footer
def write_footer_mesh(ofile):
    ofile.write("""\
  </mesh>
</dolfin>
""")

# Write graph footer
def write_footer_graph(ofile):
    ofile.write("""\
  </graph>
</dolfin>
""")

def write_header_vertices(ofile, num_vertices):
    "Write vertices header"
    print "Expecting %d vertices" % num_vertices
    ofile.write("    <vertices size=\"%d\">\n" % num_vertices)

def write_footer_vertices(ofile):
    "Write vertices footer"
    ofile.write("    </vertices>\n")
    print "Found all vertices"

def write_header_edges(ofile, num_edges):
    "Write edges header"
    print "Expecting %d edges" % num_edges
    ofile.write("    <edges size=\"%d\">\n" % num_edges)

def write_footer_edges(ofile):
    "Write edges footer"
    ofile.write("    </edges>\n")
    print "Found all edges"

def write_vertex(ofile, vertex, x, y, z):
    "Write vertex"
    ofile.write("      <vertex index=\"%d\" x=\"%s\" y=\"%s\" z=\"%s\"/>\n" % \
        (vertex, x, y, z))

def write_graph_vertex(ofile, vertex, num_edges, weight = 1):
    "Write graph vertex"
    ofile.write("      <vertex index=\"%d\" num_edges=\"%d\" weight=\"%d\"/>\n" % \
        (vertex, num_edges, weight))

def write_graph_edge(ofile, v1, v2, weight = 1):
	 "Write graph edge"
	 ofile.write("      <edge v1=\"%d\" v2=\"%d\" weight=\"%d\"/>\n" % \
        (v1, v2, weight))

def write_header_cells(ofile, num_cells):
    "Write cells header"
    ofile.write("    <cells size=\"%d\">\n" % num_cells)
    print "Expecting %d cells" % num_cells

def write_footer_cells(ofile):
    "Write cells footer"
    ofile.write("    </cells>\n")
    print "Found all cells"

def write_cell_triangle(ofile, cell, n0, n1, n2):
    "Write cell (triangle)"
    ofile.write("      <triangle index=\"%d\" v0=\"%d\" v1=\"%d\" v2=\"%d\"/>\n" % \
        (cell, n0, n1, n2))

def write_cell_tetrahedron(ofile, cell, n0, n1, n2, n3):
    "Write cell (tetrahedron)"
    ofile.write("      <tetrahedron index=\"%d\" v0=\"%d\" v1=\"%d\" v2=\"%d\" v3=\"%d\"/>\n" % \
        (cell, n0, n1, n2, n3))

def _error(message):
    "Write an error message"
    for line in message.split("\n"):
        print "*** %s" % line
    sys.exit(2)

def convert2xml(ifilename, ofilename, iformat=None):
    """ Convert a file to the DOLFIN XML format.
    """
    convert(ifilename, XmlHandler(ofilename), iformat=iformat)

def convert(ifilename, handler, iformat=None):
    """ Convert a file using a provided data handler.

    Note that handler.close is called when this function finishes.
    @param ifilename: Name of input file.
    @param handler: The data handler (instance of L{DataHandler}).
    @param iformat: Format of input file.
    """
    if iformat is None:
        iformat = format_from_suffix(os.path.splitext(ifilename)[1][1:])
    # XXX: Backwards-compat
    if hasattr(handler, "_ofilename"):
        ofilename = handler._ofilename
    # Choose conversion
    if iformat == "mesh":
        # Convert from mesh to xml format
        mesh2xml(ifilename, ofilename)
    elif iformat == "gmsh":
        # Convert from gmsh to xml format
        gmsh2xml(ifilename, handler)
    elif iformat == "Triangle":
        # Convert from Triangle to xml format
        triangle2xml(ifilename, ofilename)
    elif iformat == "xml-old":
        # Convert from old to new xml format
        xml_old2xml(ifilename, ofilename)
    elif iformat == "metis":
        # Convert from metis graph to dolfin graph xml format
        metis_graph2graph_xml(ifilename, ofilename)
    elif iformat == "scotch":
        # Convert from scotch graph to dolfin graph xml format
        scotch_graph2graph_xml(ifilename, ofilename)
    elif iformat == "diffpack":
        # Convert from Diffpack tetrahedral grid format to xml format
        diffpack2xml(ifilename, ofilename)
    elif iformat == "abaqus":
        # Convert from abaqus to xml format
        _abaqus(ifilename, handler)
    elif iformat == "NetCDF":
        # Convert from NetCDF generated from ExodusII format to xml format
        netcdf2xml(ifilename, ofilename)
    elif iformat =="ExodusII":
        # Convert from ExodusII format to xml format via NetCDF
        exodus2xml(ifilename, ofilename)
    elif iformat == "StarCD":
        # Convert from Star-CD tetrahedral grid format to xml format
        starcd2xml(ifilename, ofilename)
    else:
        _error("Sorry, cannot convert between %s and DOLFIN xml file formats." % iformat)

    # XXX: handler.close messes things for other input formats than abaqus
    if iformat == "abaqus":
        handler.close()

def starcd2xml(ifilename, ofilename):
    "Convert from Star-CD tetrahedral grid format to DOLFIN XML."

    print starcd2xml.__doc__

    if not os.path.isfile(ifilename[:-3] + "vrt") or not os.path.isfile(ifilename[:-3] + "cel"):
        print "StarCD format requires one .vrt file and one .cel file"
        sys.exit(2)


    # open output file
    ofile = open(ofilename, "w")

    # Open file, the vertices are in a .vrt file
    ifile = open(ifilename[:-3] + "vrt", "r")

    write_header_mesh(ofile, "tetrahedron", 3)


    # Read & write vertices

    # first, read all lines (need to sweep to times through the file)
    lines = ifile.readlines()

    # second, find the number of vertices
    num_vertices = -1
    counter = 0
    # nodenr_map is needed because starcd support node numbering like 1,2,4 (ie 3 is missing)
    nodenr_map = {}
    for line in lines:
        nodenr = int(line[0:15])
        nodenr_map[nodenr] = counter
        counter += 1
    num_vertices = counter

    # third, run over all vertices
    write_header_vertices(ofile, num_vertices)
    for line in lines:
        nodenr = int(line[0:15])
        vertex0 = float(line[15:31])
        vertex1 = float(line[31:47])
        vertex2 = float(line[47:63])
        write_vertex(ofile, nodenr_map[nodenr], float(vertex0), float(vertex1), float(vertex2))
    write_footer_vertices(ofile)

    # Open file, the cells are in a .cel file
    ifile = open(ifilename[:-3] + "cel", "r")

    # Read & write cells

    # first, read all lines (need to sweep to times through the file)
    lines = ifile.readlines()

    # second, find the number of cells
    num_cells = -1
    counter = 0
    for line in lines:
        l = [int(a) for a in line.split()]
        cellnr, node0, node1, node2, node3, node4, node5, node6, node7, tmp1, tmp2  = l
	if node4 > 0:
        	if node2 == node3 and node4 == node5 and node5 == node6 and node6 == node7: # these nodes should be equal
                	counter += 1
		else:
			print "The file does contain cells that are not tetraheders. The cell number is ", cellnr, " the line read was ", line
        else:
            # triangles on the surface
#            print "The file does contain cells that are not tetraheders node4==0. The cell number is ", cellnr, " the line read was ", line
            #sys.exit(2)
            pass

    num_cells = counter

    # third, run over all cells
    write_header_cells(ofile, num_cells)
    counter = 0
    for line in lines:
        l = [int(a) for a in line.split()]
        cellnr, node0, node1, node2, node3, node4, node5, node6, node7, tmp1, tmp2  = l
        if (node4 > 0):
	        if node2 == node3 and node4 == node5 and node5 == node6 and node6 == node7: # these nodes should be equal

			write_cell_tetrahedron(ofile, counter, nodenr_map[node0], nodenr_map[node1], nodenr_map[node2], nodenr_map[node4])
          		counter += 1


    write_footer_cells(ofile)
    write_footer_mesh(ofile)


    # Close files
    ifile.close()
    ofile.close()