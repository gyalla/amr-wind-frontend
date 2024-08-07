import sys
import os
import traceback
import copy
import io
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from collections import OrderedDict
import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

scriptpath = os.path.dirname(os.path.realpath(__file__))

# Load imp or importlib depending on what's available
try:
    from importlib import util
    useimp = False
except:
    import imp
    useimp = True

# See https://gist.github.com/dorneanu/cce1cd6711969d581873a88e0257e312
# for more information

"""
Plugin file structure
validateinputs/
|-- __init__.py
|-- plugin1.py
|-- plugin2.py
|-- ...
"""

# The list of all plugins is kept and built here
pluginlist = OrderedDict()
def registerplugin(f):
    """
    Register all the plugins to pluginlist
    """
    pluginlist[f.name]=f
    return f

def registeraction(alist):
    """Decorator to add action"""
    def inner(f):
        alist[f.actionname]=f
    return inner


def mergedicts(inputdict, inputdefs):
    """
    Merge the input dictionary with the task  
    """
    if bool(inputdict) is False:
        outputdict = {}
    else:
        outputdict = copy.deepcopy(inputdict)
    for key in inputdefs:
        if key['required'] and (key['key'] not in outputdict):
            # This is a problem, stop things
            raise ValueError('Required key %s not present'%key['key'])
        if (not key['required']) and (key['key'] not in outputdict):
            outputdict[key['key']] = key['default']
    return outputdict

# Small utility to automatically load modules
def load_module(path):
    name = os.path.split(path)[-1]
    if useimp:
        module = imp.load_source(name.split('.')[0], path)
    else:
        spec = util.spec_from_file_location(name, path)
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def print_readme(f, plist=pluginlist, docformat='markdown'):
    """
    Print the docs/README.md for all postpro engine executors 
    """
    header="""
# Postprocessing engine workflows

The following workflows are available:

"""
    f.write(header)
    looptasks = plist.keys()
    for task in looptasks:
        executormd = task+'.md'
        blurb      = plist[task].blurb
        f.write(f'- [{task}]({executormd}): {blurb}\n')
    return

def print_executor(f, task, docformat='markdown'):
    """
    Write the documentation page for a task
    """
    taskname = task.name
    blurb    = task.blurb
    inputdefs = task.inputdefs
    f.write(f'# {taskname}\n')
    f.write('\n')
    f.write(f'{blurb}\n')
    f.write('## Inputs: \n')
    # Write the inputs
    f.write('```\n')
    for input in inputdefs:
        if input['required']:
            extrainfo = '(Required)'
        else:
            extrainfo = '(Optional, Default: %s)'%repr(input['default'])
        f.write('  %-20s: %s %s\n'%(input['key'], input['help'], extrainfo))
    f.write('```\n\n')
    f.write('## Actions: \n')
    # Loop through the action items
    if len(task.actionlist)>0:
        f.write('```\n')
        for action in task.actionlist:
            description = task.actionlist[action].blurb
            if task.actionlist[action].required:
                description += ' (Required)'
            else:
                description += ' (Optional)'
            f.write('  %-20s: ACTION: %s\n'%(action, description))
            for input in task.actionlist[action].actiondefs:
                if input['required']:
                    extrainfo = '(Required)'
                else:
                    extrainfo = '(Optional, Default: %s)'%repr(input['default'])
                f.write('    %-18s: %s %s\n'%(input['key'], input['help'], extrainfo))
        f.write('```\n')
    # Write any examples
    if hasattr(task, 'example'):
        f.write('\n')
        f.write('## Example\n')
        f.write('```yaml')
        f.write(task.example)
        f.write('\n```\n')
    return

def makedocs(rootpath=scriptpath, docdir='doc', docformat='markdown'):
    """
    Create the documentation directory
    """
    docpath = os.path.join(rootpath, docdir)
    if not os.path.exists(docpath):
        os.makedirs(docpath)
        
    with open(os.path.join(docpath, 'README.md'), 'w') as f:
        print_readme(f)

    looptasks = pluginlist.keys()
    for task in looptasks:
        mdfile = os.path.join(docpath, pluginlist[task].name+'.md')
        print(mdfile)
        with open(mdfile, 'w') as f:
            print_executor(f, pluginlist[task])
    return

def print_inputs(subset=[], plist=pluginlist):
    """
    Prints out the inputs required for every plugin
    """
    if len(subset)>0:
        looptasks = subset
    else:
        looptasks = plist.keys()
    for task in looptasks:
        # Print out info on each task
        inputdefs = plist[task].inputdefs
        print('---')
        print(task+': '+plist[task].blurb)
        for input in inputdefs:
            if input['required']:
                extrainfo = '(Required)'
            else:
                extrainfo = '(Optional, Default: %s)'%repr(input['default'])
            print('  %-20s: %s %s'%(input['key'], input['help'], extrainfo))
        # Loop through the action items
        if len(plist[task].actionlist)>0:
            for action in plist[task].actionlist:
                description = plist[task].actionlist[action].blurb
                if plist[task].actionlist[action].required:
                    description += ' (Required)'
                else:
                    description += ' (Optional)'
                print('  %-20s: ACTION: %s'%(action, description))
                for input in plist[task].actionlist[action].actiondefs:
                    if input['required']:
                        extrainfo = '(Required)'
                    else:
                        extrainfo = '(Optional, Default: %s)'%repr(input['default'])
                    print('    %-18s: %s %s'%(input['key'], input['help'], extrainfo))
        if hasattr(plist[task], 'example'):
            print()
            print('Example')
            print('-------')
            print(plist[task].example)
        print()
    return

# =====================================================
# --- ADD REUSABLE CLASSES AND METHODS HERE ---
# =====================================================
def convert_pt_axis1axis2_to_xyz(ptlist, origin, axis1, axis2, axis3, offsets, iplane):
    """
    Converts the location of pt given in natural plane (axis1-axis2) coordinates
    to global xyz coordinates
    """
    offsetlist = [offsets] if (not isinstance(offsets, list)) and (not isinstance(offsets,np.ndarray)) else offsets
    # Compute the normals
    n1 = axis1/np.linalg.norm(axis1)
    n2 = axis2/np.linalg.norm(axis2)
    if np.linalg.norm(axis3) > 0.0:
        n3 = axis3/np.linalg.norm(axis3)
    else:
        n3 = axis3
    # compute the coordinates in the global XYZ frame
    porigin = origin + n3*offsetlist[iplane]
    pt_xyz = []
    for pt in ptlist:
        pt_xyz.append(porigin + pt[0]*n1 + pt[1]*n2)
    return pt_xyz

def convert_pt_xyz_to_axis1axis2(ptlist, origin, axis1, axis2, axis3, offsets, iplanevec):
    """
    Converts the location of pt given in global xyz coordinates to 
    to natural plane (axis1-axis2) coordinates

    Note: assumes that pt lies on the plane given by iplane
    """
    offsetlist = [offsets] if (not isinstance(offsets, list)) and (not isinstance(offsets,np.ndarray)) else offsets    
    # Compute the normals
    n1 = axis1/np.linalg.norm(axis1)
    n2 = axis2/np.linalg.norm(axis2)
    if np.linalg.norm(axis3) > 0.0:
        n3 = axis3/np.linalg.norm(axis3)
    else:
        n3 = axis3

    R = np.array([n1,n2,n3])

    porigin = np.full_like(ptlist, 0.0)
    for ipt in range(len(ptlist)):
        porigin[ipt,:] = origin + n3*offsetlist[iplanevec[ipt]]

    dv = (np.array(ptlist) - np.array(porigin))
    avec = R@dv.T
    returnvec = avec.T
    return returnvec[:,0:2]

def project_pt_to_plane(pt, origin, axis1, axis2, axis3, offsets, iplane):
    """
    Projects the point pt to the plane

    See https://math.stackexchange.com/questions/100761/how-do-i-find-the-projection-of-a-point-onto-a-plane
    """
    # Compute the normals
    n1 = axis1/np.linalg.norm(axis1)
    n2 = axis2/np.linalg.norm(axis2)
    if np.linalg.norm(axis3) > 0.0:
        n3 = axis3/np.linalg.norm(axis3)
    else:
        n3 = axis3
    # origin of the plane
    porigin = origin + n3*offsets[iplane]
    # Normal of the plane
    pnormal = np.cross(n1, n2)

    dv = pt - porigin
    v_parallel = np.dot(dv, pnormal)*pnormal
    v_perp     = dv - v_parallel
    
    p_proj     = pt + v_perp
    return p_proj

def compute_axis1axis2_coords(db):
    """
    Computes the native axis1 and axis2 coordinate system for a given
    set of sample planes.

    Note: this assumes db has the origin, axis1/2, and offset definitions
    """

    # Check to make sure db has everything needed
    if ('origin' not in db) or \
       ('axis1' not in db) or \
       ('axis2' not in db) or \
       ('axis3' not in db) or \
       ('offsets') not in db:
        print('Need to ensure that the sample plane data includes origin, axis1, axis2, axis3, and offset information')
        return

    # Pull out the coordate definitions
    axis1  = np.array(db['axis1'])
    axis2  = np.array(db['axis2'])
    axis3  = np.array(db['axis3'])
    origin = np.array(db['origin'])
    offsets= db['offsets']
    if (not isinstance(offsets,list)) and (not isinstance(offsets,np.ndarray)):
        offsets = [offsets]

    # Create the iplane matrices
    iplanemat = np.full_like(db['x'], 0, dtype=np.int64)
    for k in range(len(offsets)):
        iplanemat[k,:,:] = k

    # create list of points
    xyz_pt    = np.vstack([db['x'].ravel(), db['y'].ravel(), db['z'].ravel()])

    avec = convert_pt_xyz_to_axis1axis2(xyz_pt.T, origin, axis1, axis2, axis3, offsets, iplanemat.ravel())
    db['a1'] = avec[:,0].reshape(db['x'].shape)
    db['a2'] = avec[:,1].reshape(db['y'].shape)
    return

def interp_db_pts(db, ptlist, iplanelist, varnames, pt_coords='XYZ', timeindex=None, method='linear'):
    """
    Interpolate a series of points from the db plane variables
    """
    # Make sure iplanelist is a list
    if not isinstance(iplanelist, list):
        iplanelist = [iplanelist]
        
    if not isinstance(timeindex, list):
        timeindex = [timeindex]

    # Make sure db has the natural plane coordinates
    if ('a1' not in db) or \
       ('a2' not in db) or \
       ('a3' not in db):
        compute_axis1axis2_coords(db)

    # Initialize the interpdat vector
    interpdat = {'a1':np.array([]), 'a2':np.array([]),
                 'x':np.array([]), 'y':np.array([]), 'z':np.array([]),
    }
    if timeindex[0] is not None:
        interpdat['time'] = np.array([])
    for var in varnames:
        interpdat[var] = np.array([])

    # Loop through each iplane list
    for iplane in iplanelist:
        if pt_coords=='XYZ':
            # Convert points to a1/a2 coordinate system
            pt_coords_xyz = np.array(ptlist)
            pt_coords_a1a2 = convert_pt_xyz_to_axis1axis2(ptlist, db['origin'], db['axis1'], db['axis2'],
                                                          db['axis3'], db['offsets'], [iplane]*len(ptlist))
        else:
            # Already in the a1/a2 coordinate system
            pt_coords_xyz  = []
            pt_coords_a1a2 = np.array(ptlist)
            pt_coords_xyz = convert_pt_axis1axis2_to_xyz(pt_coords_a1a2, db['origin'], db['axis1'], db['axis2'],
                                                         db['axis3'], db['offsets'], iplane)
            pt_coords_xyz = np.array(pt_coords_xyz)
        ptswap = np.array(pt_coords_a1a2)[:,[1,0]]
        
        for i, tindex in enumerate(timeindex):
            interpdat['a1'] = np.append(interpdat['a1'], pt_coords_a1a2[:,0])
            interpdat['a2'] = np.append(interpdat['a2'], pt_coords_a1a2[:,1])
            interpdat['x'] = np.append(interpdat['x'], pt_coords_xyz[:,0])
            interpdat['y'] = np.append(interpdat['y'], pt_coords_xyz[:,1])
            interpdat['z'] = np.append(interpdat['z'], pt_coords_xyz[:,2])
            if tindex is not None:
                interptime = db['times'][i]
                interpdat['time'] = np.append(interpdat['time'], np.ones(len(ptswap))*interptime)
            # Go through each variable and interpolate
            for var in varnames:
                a1vec = db['a1'][iplane,0,:]
                a2vec = db['a2'][iplane,:,0]
                interpcoords = (a2vec, a1vec)
                if tindex is None:
                    dbvar = db[var][iplane,:,:]
                else:
                    dbvar = db[var][tindex][iplane,:,:]
                interpfunc = RegularGridInterpolator(interpcoords, dbvar, method=method)
                #Add to the interpdat
                interpdat[var] = np.append(interpdat[var], interpfunc(ptswap))
    return interpdat

# ------- reusable circumferential avg class ----------
class circavgtemplate():
    """
    Circumferential average data (create radial profiles)
    """
    actionname = 'circavg'
    blurb      = 'Circumferential average data into radial profiles'
    required   = False
    actiondefs = [
        {'key':'centerpoint', 'required':True,  'default':[0,0],
         'help':'Center point to use for radial averaging',},
        {'key':'r1', 'required':True,  'default':0.0,
         'help':'Inner radius',},
        {'key':'r2', 'required':True,  'default':0.0,
         'help':'Outer radius',},
        {'key':'Nr', 'required':True,  'default':100,
         'help':'Number of points in radial direction',},
        {'key':'pointcoordsystem', 'required':True,  'default':'',
         'help':'Coordinate system for point interpolation.  Options: XYZ, A1A2',},
        {'key':'varnames', 'required':True,  'default':['velocityx','velocityy','velocityz'],
         'help':'List of variable names to average.',},
        {'key':'savefile',  'required':True,  'default':'',
         'help':'Filename to save the radial profiles', },
        {'key':'iplane',   'required':False,  'default':0,
         'help':'Which plane(s) to interpolate on', },
        {'key':'theta1', 'required':False,  'default':0.0,
         'help':'Theta start',},
        {'key':'theta2', 'required':False,  'default':2*np.pi,
         'help':'Theta end',},
        {'key':'Ntheta', 'required':False,  'default':180,
         'help':'Number of points in theta',},
    ]

    interpdb = None
    def __init__(self, parent, inputs):
        self.actiondict = mergedicts(inputs, self.actiondefs)
        self.parent = parent
        # Don't forget to initialize interpdb in inherited classes!
        print('Initialized '+self.actionname+' inside '+parent.name)
        return

    def execute(self):
        print('Executing '+self.actionname)
        # Get inputs
        centerpoint_in  = self.actiondict['centerpoint']
        r1              = self.actiondict['r1']
        r2              = self.actiondict['r2']
        Nr              = self.actiondict['Nr']
        varnames        = self.actiondict['varnames']
        Ntheta          = self.actiondict['Ntheta']
        iplanes         = self.actiondict['iplane']
        pointcoordsystem = self.actiondict['pointcoordsystem']
        savefile        = self.actiondict['savefile']
        theta1          = self.actiondict['theta1']
        theta2          = self.actiondict['theta2']

        # Make sure db has the natural plane coordinates
        if ('a1' not in self.interpdb) or \
           ('a2' not in self.interpdb) or \
           ('a3' not in self.interpdb):
            compute_axis1axis2_coords(self.interpdb)

        thetavec = np.linspace(theta1, theta2, Ntheta, endpoint=False)
        rvec     = np.linspace(r1, r2, Nr)

        # Loop through each plane
        if not isinstance(iplanes, list): iplanes = [iplanes,]

        for iplane in iplanes:
            iplane = int(iplane)
            print('iplane = ',iplane)
            # Create the holding vectors
            Rprofiledat = {'r':[]}

            for v in varnames:
                Rprofiledat[v] = []

            # Transform the centerpoint if necessary
            ptlist = [centerpoint_in]
            if pointcoordsystem == 'XYZ':
                ptlist_a1a2 = convert_pt_xyz_to_axis1axis2(ptlist, self.interpdb['origin'],
                                                           self.interpdb['axis1'], self.interpdb['axis2'],
                                                           self.interpdb['axis3'], self.interpdb['offsets'], [iplane]*len(ptlist))
                center_a1a2 = ptlist_a1a2[0]
            else:
                ptlist_xyz = convert_pt_axis1axis2_to_xyz(ptlist, self.interpdb['origin'],
                                                          self.interpdb['axis1'], self.interpdb['axis2'],
                                                          self.interpdb['axis3'], self.interpdb['offsets'], [iplane]*len(ptlist))
                center_a1a2 = centerpoint_in

            planeoffset = self.interpdb['offsets'][iplane]

            # Create the circle of averaging points
            for R in rvec:
                thetapoints = []
                for theta in thetavec:
                    x, y = center_a1a2[0] + R*np.cos(theta), center_a1a2[1] + R*np.sin(theta)
                    thetapoints.append([x,y])
                thetapoints = np.array(thetapoints)
                interpdat = interp_db_pts(self.interpdb, thetapoints, [iplane], varnames, pt_coords='A1A2', timeindex=None, method='linear')
                Rprofiledat['r'].append(R)
                for v in varnames:
                    Rprofiledat[v].append(np.mean(interpdat[v]))

            # Save data to csv file
            dfcsv = pd.DataFrame()
            for k, g in Rprofiledat.items():
                dfcsv[k] = g
            dfcsv.to_csv(savefile.format(iplane=iplane),index=False,sep=',')

        return

# ------- reusable interpolation class ----------------
class interpolatetemplate():
    """
    An interpolation template that can be used by other executors
    """
    actionname = 'interpolate'
    blurb      = 'Interpolate data from an arbitrary set of points'
    required   = False
    actiondefs = [
        {'key':'pointlocationfunction', 'required':True,  'default':'',
         'help':'Function to call to generate point locations. Function should have no arguments and return a list of points',},
        {'key':'pointcoordsystem', 'required':True,  'default':'',
         'help':'Coordinate system for point interpolation.  Options: XYZ, A1A2',},
        {'key':'varnames', 'required':True,  'default':['velocityx','velocityy','velocityz'],
         'help':'List of variable names to extract.',},
        {'key':'savefile',  'required':False,  'default':'',
         'help':'Filename to save the interpolated data', },
        {'key':'method',  'required':False,  'default':'linear',
         'help':'Interpolation method [Choices: linear, nearest, slinear, cubic, quintic, pchip]', },
        {'key':'iplane',   'required':False,  'default':0,
         'help':'Which plane to interpolate on', },
        {'key':'iters',    'required':False,  'default':None,
         'help':'Which time iterations to interpolate from', },
    ]

    interpdb = None
    iters    = None
    def __init__(self, parent, inputs):
        self.actiondict = mergedicts(inputs, self.actiondefs)
        self.parent = parent
        print('Initialized '+self.actionname+' inside '+parent.name)
        # Don't forget to initialize interpdb in inherited classes!
        return

    def execute(self):
        print('Executing '+self.actionname)
        pointlocfunc      = self.actiondict['pointlocationfunction']
        pointcoordsystem  = self.actiondict['pointcoordsystem']
        varnames          = self.actiondict['varnames']
        iplane            = self.actiondict['iplane']        
        savefile          = self.actiondict['savefile']
        method            = self.actiondict['method']
        #iters             = self.actiondict['iters']

        # Get the point locations from the udf
        modname  = pointlocfunc.split('.')[0]
        funcname = pointlocfunc.split('.')[1]
        func = getattr(sys.modules[modname], funcname)
        ptlist = func()

        # interpolate data
        interpdat = interp_db_pts(self.interpdb, ptlist, iplane, varnames,
                                  pt_coords=pointcoordsystem, timeindex=self.iters,
                                  method=method)
        #print(interpdat)
        # Save the output to a csv file
        if len(savefile)>0:
            dfcsv = pd.DataFrame()
            for k, g in interpdat.items():
                dfcsv[k] = g
            dfcsv.to_csv(savefile,index=False,sep=',')
            
        return

    
# ------- reusable contour plot class -----------------
class contourplottemplate():
    """
    A contour plot template that can be used by other executors
    """
    actionname = 'plot'
    blurb      = 'Plot rotor averaged planes'
    required   = False
    actiondefs = [
        {'key':'dpi',       'required':False,  'default':125,
         'help':'Figure resolution', },
        {'key':'figsize',   'required':False,  'default':[12,8],
         'help':'Figure size (inches)', },
        {'key':'savefile',  'required':False,  'default':'',
         'help':'Filename to save the picture', },
        {'key':'clevels',   'required':False,  'default':'41', 
         'help':'Color levels (eval expression)',},
        {'key':'iplane',   'required':False,  'default':0,
         'help':'Which plane to pull from netcdf file', },            
        {'key':'xaxis',    'required':False,  'default':'x',
         'help':'Which axis to use on the abscissa', },
        {'key':'yaxis',    'required':False,  'default':'y',
         'help':'Which axis to use on the ordinate', },            
        {'key':'xlabel',    'required':False,  'default':'X [m]',
         'help':'Label on the X-axis', },
        {'key':'ylabel',    'required':False,  'default':'Y [m]',
         'help':'Label on the Y-axis', },
        {'key':'title',     'required':False,  'default':'',
         'help':'Title of the plot',},
        {'key':'plotfunc',  'required':False,  'default':'lambda db: 0.5*(db["uu_avg"]+db["vv_avg"]+db["ww_avg"])',
         'help':'Function to plot (lambda expression)',},
    ]
    plotdb = None
    def __init__(self, parent, inputs):
        self.actiondict = mergedicts(inputs, self.actiondefs)
        self.parent = parent
        print('Initialized '+self.actionname+' inside '+parent.name)
        # Don't forget to initialize plotdb in inherited classes!
        return

    def execute(self):
        print('Executing '+self.actionname)
        figsize  = self.actiondict['figsize']
        xaxis    = self.actiondict['xaxis']
        yaxis    = self.actiondict['yaxis']
        dpi      = self.actiondict['dpi']
        iplanes  = self.actiondict['iplane']
        savefile = self.actiondict['savefile']
        xlabel   = self.actiondict['xlabel']
        ylabel   = self.actiondict['ylabel']
        clevels  = eval(self.actiondict['clevels'])
        title    = self.actiondict['title']
        plotfunc = eval(self.actiondict['plotfunc'])
        if not isinstance(iplanes, list): iplanes = [iplanes,]

        # Convert to native axis1/axis2 coordinates if necessary
        if ('a1' in [xaxis, yaxis]) or \
           ('a2' in [xaxis, yaxis]) or \
           ('a3' in [xaxis, yaxis]):
            compute_axis1axis2_coords(self.plotdb)
        
        for iplane in iplanes:
            fig, ax = plt.subplots(1,1,figsize=(figsize[0],figsize[1]), dpi=dpi)
            plotq = plotfunc(self.plotdb)
            c=plt.contourf(self.plotdb[xaxis][iplane,:,:], 
                           self.plotdb[yaxis][iplane,:,:], plotq[iplane, :, :], 
                           levels=clevels,cmap='coolwarm', extend='both')
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="3%", pad=0.05)
            cbar=fig.colorbar(c, ax=ax, cax=cax)
            cbar.ax.tick_params(labelsize=7)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.axis('scaled')
            ax.set_title(eval("f'{}'".format(title)))

            if len(savefile)>0:
                savefname = savefile.format(iplane=iplane)
                plt.savefig(savefname)
        return

# =====================================================

    
def runtaskdict(taskdict, plist, looptasks, verbose):
    for task in looptasks:
        if task in taskdict:
            taskitem = plist[task](taskdict[task], verbose=verbose)
            taskitem.execute(verbose=verbose)
    return
    
def driver(yamldict, plist=pluginlist, verbose=None):
    """
    Run through and execute all tasks
    """
    looptasks = plist.keys()

    # Get the global attributes
    globattr = yamldict['globalattributes'] if 'globalattributes' in yamldict else {}
    
    # Set the verbosity
    # Take verbosity from globalattributes
    verbose_attr = globattr['verbose'] if 'verbose' in globattr else False
    # Override with verbose if necessary
    verbosity = verbose if verbose is not None else verbose_attr

    # Load any user defined modules
    if 'udfmodules' in globattr:
        udfmodules = globattr['udfmodules']
        for module in udfmodules:
            name = os.path.splitext(os.path.basename(module))[0]
            mod = load_module(module)
            sys.modules[name] = mod

            
    # Check if executeorder is present
    if 'executeorder' in globattr:
        exeorder = globattr['executeorder']
        for item in exeorder:
            if isinstance(item, str):
                if item in plist.keys():
                    # item is the exact name of an executor, run it:
                    taskitem = plist[item](yamldict[item], verbose=verbosity)
                    taskitem.execute(verbose=verbosity)
                else:
                    # item is an entire workflow, run that
                    runtaskdict(yamldict[item], plist, looptasks, verbosity)
            else:
                # item is a workflow with a specific set of tasks
                wflowname  = next(iter(item))
                wflowtasks = item[wflowname]
                runtaskdict(yamldict[wflowname], plist, wflowtasks, verbosity)
    else:
        # Run everything in yamldict
        runtaskdict(yamldict, plist, looptasks, verbosity)  
    return


def test():
    # Only execute this if test.py is included
    yamldict = {
        'task1':[{'name':'MyTask1',
                 'filename':'myfile',
                 'action1':{'name':'myaction'}}],
        'task2':{'name':'MyTask2', 'filename':'myfile2', },
    }
    driver(yamldict)
    return

# ------------------------------------------------------------------
# Get current path
path    = os.path.abspath(__file__)
dirpath = os.path.dirname(path)

# Load all plugins in this directory
for fname in sorted(os.listdir(dirpath)):
    # Load only "real modules"
    if not fname.startswith('.') and \
       not fname.startswith('__') and fname.endswith('.py'):
        try:
            load_module(os.path.join(dirpath, fname))
        except Exception:
            traceback.print_exc()

