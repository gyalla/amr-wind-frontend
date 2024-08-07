# convert

Converts netcdf sample planes to different file formats
## Inputs: 
```
  name                : An arbitrary name (Required)
  ncfile              : NetCDF sampling file (Required)
  group               : Which group to pull from netcdf file (Optional, Default: None)
  trange              : Which times to pull from netcdf file, e.g., [tstart,tend] (Required)
```

## Actions: 
```
  bts                 : ACTION: Converts data to bts files (Optional)
    iplane            : Index of x location to read (Required)
    yhh               : Hub height location in y (Required)
    zhh               : Hub height location in z (Required)
    btsfile           : bts file name to save results (Required)
    ID                : bts file ID. 8="periodic", 7="non-periodic" (Optional, Default: 8)
```
