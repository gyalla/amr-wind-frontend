#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

#
# Copyright (c) 2022, Alliance for Sustainable Energy
#
# This software is released under the BSD 3-clause license. See LICENSE file
# for more details.
#

import sys, os, re
from collections            import OrderedDict 
import numpy as np
import fileinput

scriptpath = os.path.dirname(os.path.realpath(__file__))
utilpath   = os.path.join(scriptpath, 'utilities')
sys.path.insert(1, utilpath)
import findOFversion as findOFversion

import argparse
import ast

try:
    import argcomplete
    has_argcomplete = True
except:
    has_argcomplete = False

def is_number(s):
    try:
        complex(s) # for int, long, float and complex
    except ValueError:
        return False
    return True

def editFASTfile(FASTfile, replacedict, tagedits=True):
    commentchars = ['=', '#']
    OutListCount = 0
    for line in fileinput.input(FASTfile, inplace=True, backup='.bak'):
        #sys.stdout.write("# "+line)
        linesplit=re.split('[, ;]+', line.strip())
        outline=""
        # Check to make sure the line doesn't start with comment char
        firstchar = ""
        if len(line.strip())>0: firstchar = line.strip()[0]
        if firstchar in commentchars: 
            outline=str(line)
        # Edit the Outlist if applicable
        if (linesplit[0]=='OutList'):
            if ('OutList' in replacedict.keys()) or ('OutList'+repr(OutListCount) in replacedict.keys()):
                targetkey = 'OutList' if 'OutList' in replacedict.keys() else 'OutList'+repr(OutListCount)
                sys.stderr.write('Adding %s to OutList\n'%(repr(replacedict[targetkey])))
                outline = str(line)
                outline += replacedict[targetkey]+'\n'
            OutListCount += 1
        else:
            # Ignore any lines with less than two items
            if len(linesplit)<2:
                outline=str(line)
            
        # Check to make sure line is not all numbers
        allnums = [is_number(x) for x in linesplit]
        if False not in allnums:
            outline=str(line)

        # Handle list of nodes
        if outline=="":
            idx = 1
            if is_number(linesplit[idx]):
                # Find the right keyword
                idx = allnums.index(False)

            keyword = linesplit[idx]
            if keyword in replacedict.keys():
                replacestring = repr(replacedict[keyword]).replace("'",'')
                outline  = '%10s '%replacestring 
                outline += ' '.join(linesplit[idx:])
                if tagedits: outline += ' [EDITED]'
                outline += '\n'
                sys.stderr.write(outline)
            else:
                outline=line

        # Write out the line
        sys.stdout.write(outline)
    return

def editDISCONfile(DISCONfile, replacedict):
    """
    Edits a value in the DISCON file
    """
    findsubstring = lambda s, start, end: s.split(start)[1].split(end)[0]
    commentchars = ['!']
    iline = 0
    for line in fileinput.input(DISCONfile, inplace=True, backup='.bak'):
        outline=""
        # Ignore the line if it starts with a comment
        if len(line.strip())>0: firstchar = line.strip()[0]
        if firstchar in commentchars: 
            outline=str(line)
        
        # Replace the line by number
        linekey = 'line'+str(iline)
        if linekey in replacedict.keys():
            outline = replacedict[linekey]+'\n'
            sys.stderr.write('replacing line %i with \n%s'%(iline, outline))
            
        # Look for a keyword in the discon file
        keystart = '!'
        keyend   = '-'
        try:
            keyword = findsubstring(line, keystart, keyend).strip()
        except:
            keyword = None
        if (keyword is not None) and keyword in replacedict.keys():
            # Replace everything in the beginning of the line
            linesplit = line.split(keystart, 1)
            endline = linesplit[1].strip()
            outline = str(replacedict[keyword])+' ! '+endline+' [EDITED]\n'
            sys.stderr.write(outline)            
            
        # If nothing needs to be modified in the line, keep it original
        if outline=="":
            outline=line
        # Write out the line
        sys.stdout.write(outline)
        iline += 1
    return

def getVarFromDISCON(disconfile, key):
    commentchars = ['!']
    findsubstring = lambda s, start, end: s.split(start)[1].split(end)[0]
    keystart = '!'
    keyend   = '-'
    with open(disconfile) as fp:
        line=fp.readline()
        while line:
            # Look for a keyword in the discon file
            try:
                keyword = findsubstring(line, keystart, keyend).strip()
            except:
                keyword = None
            if (keyword is not None) and (keyword == key):
                return line.split(keystart)[0]
            line=fp.readline()
    # Key not found
    return None

def FASTfile2dict(FASTfile):
    """
    Reads the file FASTfile and returns a dictionary with parameters
    """
    commentchars = ['=', '#']
    d = OrderedDict()
    # go through the file line-by-line
    with open(FASTfile) as fp:
        line=fp.readline()
        while line:
            # Check to make sure the line doesn't start with comment char
            firstchar = ""
            if len(line.strip())>0: firstchar = line.strip()[0]
            if firstchar in commentchars: 
                line=fp.readline()
                continue
            #linesplit=line.strip().split(", ")
            linesplitX=re.split('[, ;]+', line.strip())
            # Remove any empty tokens in linesplit
            linesplit=[x.strip() for x in linesplitX if x.strip() != '']

            # Ignore any lines with less than two items
            if len(linesplit)<2:
                line=fp.readline()
                continue          

            # Check to make sure line is not all numbers
            allnums = [is_number(x) for x in linesplit]
            if False not in allnums:
                line=fp.readline()
                continue          
                
            # Handle the outlist
            if linesplit[0]=="OutList":
                outlistline = fp.readline()
                outlistlinesplit = outlistline.strip().split()
                firstword   = "" if len(outlistlinesplit)==0 else outlistlinesplit[0]
                outlist     = []
                while firstword != "END":
                    outlist.append(outlistline.strip())
                    outlistline = fp.readline()
                    outlistlinesplit = outlistline.strip().split()
                    firstword   = "" if len(outlistlinesplit)==0 else outlistlinesplit[0]

                # Check how many other Outlists there are:
                keylist = [k for k,g in d.items()]
                numOutList=len([x for x in keylist if x.startswith('OutList')])
                suffix = repr(numOutList) if numOutList>0 else ''
                d["OutList"+suffix] = outlist
                line = fp.readline()
                continue

            # Handle list of nodes
            idx = 1
            if is_number(linesplit[idx]):
                # Find the right keyword
                idx = allnums.index(False)

            keyword = linesplit[idx]
            if idx==1:
                d[keyword] = linesplit[0]
            else:
                d[keyword] = linesplit[:idx]

            line=fp.readline()
    return d

def getFileFromFST(fstfile, key, fstdict=None):
    """
    Get the file referenced by key in fstfile
    """
    if fstdict is None:
        fstdict=FASTfile2dict(fstfile)
    keyfile = fstdict[key].strip('"').strip("'")
    # Now set up the path to keyfile correctly
    fstpath = os.path.dirname(os.path.abspath(fstfile))
    return os.path.join(fstpath, keyfile)

def getVarFromFST(fstfile, key, fstdict=None):
    """
    Get the file referenced by key in fstfile
    """
    if fstdict is None:
        fstdict=FASTfile2dict(fstfile)
    if key in fstdict:
        return fstdict[key]
    else:
        return None

def loadoutfile(filename):
    """
    Loads the FAST output file
    """
    # load the data file  
    dat=np.loadtxt(filename, skiprows=8)
    # get the headers and units
    with open(filename) as fp:
        fp.readline() # blank  
        fp.readline() # When FAST was run
        fp.readline() # linked with...   
        fp.readline() # blank            
        fp.readline() # Description of FAST input file
        fp.readline() # blank                         
        varsline=fp.readline()
        unitline=fp.readline()
        headers=varsline.strip().split()
        units  =unitline.strip().split()
    return dat, headers, units

def loadalldata(allfiles):
    """
    Load all data files given in allfiles
    """
    adat=[]
    header0=[]
    units0=[]
    names=[]
    for ifile, file in enumerate(allfiles):
        names.append(file)
        print("Loading file "+file)
        dat, headers, units = loadoutfile(file)
        adat.append(dat)
        if ifile==0:
            header0 = headers
            units0   = units
        else:
            if ((len(header0) != len(headers)) or (len(units0)!=len(units))):
                print("Data sizes doesn't match")
                sys.exit(1)
    return adat, header0, units0, names

def getDensity(fstfile, verbose=False):
    """
    Gets the density in OpenFAST input file
    """
    # Get the version of the fstfile
    ver, match = findOFversion.findversion(fstfile)
    if verbose: print("Version: "+repr(ver))
    if (match != findOFversion.versionmatch.MATCH):
        print("No matching version found for "+fstfile)
        sys.exit(1)
        return
    # Get the AeroFile
    AeroFile      = getVarFromFST(fstfile, 'AeroFile').strip('"')
    AeroFileWPath = os.path.join(os.path.dirname(fstfile), AeroFile)
    AirDens       = getVarFromFST(AeroFileWPath,'AirDens')

    verindex   = findOFversion.convertversiontoindex((ver['major'], ver['minor']))
    ver31index = findOFversion.convertversiontoindex((3,1))
    if verindex < ver31index:
        # Just get density from the AeroFile
        if verbose: print("Density from aerofile: %f"%float(AirDens))
        return float(AirDens)
    else:
        # Check the density from AeroFile
        AirDensString = AirDens.replace('"', '').replace("'",'').lower()
        if verbose: print("Density from aerofile: %s"%AirDensString)
        if AirDensString == "default":
            # Get density from fst file
            fstdensity = getVarFromFST(fstfile, 'AirDens')
            if verbose: print("Using density from fst file: %s"%fstdensity)
            return float(fstdensity)
        else:
            return float(AirDensString)
    return

def setDensity(fstfile, density, verbose=False):
    """
    Sets the density in OpenFAST input file
    """
    # Get the version of the fstfile
    ver, match = findOFversion.findversion(fstfile)
    if verbose: print("Version: "+repr(ver))
    if (match != findOFversion.versionmatch.MATCH):
        print("No matching version found for "+fstfile)
        sys.exit(1)
        return

    verindex   = findOFversion.convertversiontoindex((ver['major'], ver['minor']))
    ver31index = findOFversion.convertversiontoindex((3,1))
    if verindex < ver31index:
        # Set density in the AeroFile
        # Get the AeroFile
        AeroFile      = getVarFromFST(fstfile, 'AeroFile').strip('"')
        AeroFileWPath = os.path.join(os.path.dirname(fstfile), AeroFile)
        editFASTfile(AeroFileWPath, {'AirDens':density})
        if verbose:
            print("Set AirDens in %s: %f"%(AeroFile, float(AirDens)))
    else:
        # Set density in the FST file
        editFASTfile(fstfile, {'AirDens':density})
        if verbose:
            print("Set AirDens in %s: %f"%(fstfile, float(AirDens)))
    return

# ========================================================================
#
# Main
#
# ========================================================================
if __name__ == "__main__":
    helpstring = """
    Edit an openFAST model
    """
    
    # Handle arguments
    parser     = argparse.ArgumentParser(description=helpstring,
                                         formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument(
        "fstfile",
        help="input FST file",
        type=str,
    )

    parser.add_argument(
        "editfile",
        help="File to edit",
        choices=['fstfile', 'AeroFile', 'ServoFile', 'EDFile', 'HydroFile','DISCON'],
        type=str,
    )

    parser.add_argument(
        "params",
        help="String with dictionary of parameters to edit",
    )

    parser.add_argument('--notagedits', 
                        help="Do not tag edits in the openfast files",
                        default=False,
                        action='store_true')

    # Load the options
    if has_argcomplete: argcomplete.autocomplete(parser)    
    args      = parser.parse_args()
    fstfile   = args.fstfile
    editfile  = args.editfile
    params    = ast.literal_eval(args.params)
    notagedits = args.notagedits

    if editfile == 'fstfile':
        editFASTfile(fstfile, params, tagedits=(not notagedits))
    elif editfile == 'DISCON':
        SDfile = getFileFromFST(fstfile, 'ServoFile')
        DISCONfile   = getFileFromFST(SDfile, 'DLL_InFile')
        editDISCONfile(DISCONfile, params)
    else:
        OFfile = OpenFAST.getFileFromFST(fstfile, editfile)
        editFASTfile(OFfile, params, tagedits=(not notagedits))
