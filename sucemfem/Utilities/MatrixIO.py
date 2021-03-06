## Copyright (C) 2011 Stellenbosch University
##
## This file is part of SUCEM.
##
## SUCEM is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## SUCEM is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with SUCEM. If not, see <http://www.gnu.org/licenses/>. 
##
## Contact: cemagga@gmail.com 
# Authors:
# Evan Lezar <mail@evanlezar.com>

"""
This is a collection of routines to save and load finite element matrices to disk
"""
import os
import numpy as np

def check_path ( path, create=True ):
    """
    Check to see if a path exists, and create it if desired
    
    @param path: the path whose existence must be checked
    @param create: True by default. Create the path if it doesn't exist
    
    @return: True or False depending on whether the path exists after the function has executed
    """
    if not os.path.exists( path ):
        if not create:
            return True
        os.makedirs( path )
    return True

def save_scipy_matrix_as_mat ( path, name, matrix ):
    """
    Save a scipy sparse matrix as a .mat file.
    
    @param path: the folder in which the matrix is to be saved
    @param name: the filename of the matrix
    @param matrix: the scipy matrix to save
    """
    import scipy.io
    if not check_path ( path ):
        return False
    
    scipy.io.savemat ( os.path.join(path, name), {name: matrix }, oned_as='column' )
    
    return True


def load_scipy_matrix_from_mat ( path, name ):
    """
    Load a scipy sparse matrix from a .mat file.
    
    @param path: the folder in which the matrix is saved
    @param name: the filename of the matrix
    """
    import scipy.io
    import scipy.sparse
    
    filename =  os.path.join ( path, name)
    
    if not os.path.exists( filename + '.mat' ):
        return None
    
    data = scipy.io.loadmat ( filename )[name]
    
    if type(data) is np.ndarray:
        matrix = data
    else:
        matrix = data.tocsr ()
         
    return matrix
    
    
    
