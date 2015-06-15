#!/usr/bin/env python
#
############################################################################
#
# MODULE:       r.contour.evolution
# AUTHOR(S):    Vaclav Petras
# PURPOSE:      Spatio-temporal contour vector field terrain analysis tool
#
# COPYRIGHT:    (C) 2014 by Vaclav Petras and the GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
#############################################################################


#%module
#% description: Outputs raster maps prepared for a Leaflet web map
#% keywords: raster
#% keywords: export
#% keywords: visualization
#% keywords: web
#%end
#%option G_OPT_R_INPUT
#% key: raster
#% label: Name(s) of input raster map(s)
#% description: Either this or strds option must be used to specify the input.
#% multiple: yes
#% required: yes
#%end
#%option
#% key: years
#% type: integer
#% label: Years
#% description: Must be same count of rasters
#% multiple: yes
#% required: yes
#%end
#%option
#% key: level
#% type: double
#% label: Contour level
#% description: Contour level where raster map with vector field will be generated
#% multiple: no
#% required: yes
#%end


# -*- coding: utf-8 -*-
"""
Created on Fri Feb 14 22:49:47 2014

@author: Vaclav Petras
"""

import os

import grass.script.core as gcore
from grass.script.core import parse_command, parse_key_val
from grass.pygrass.modules import Module as run_command
from grass.gunittest.gmodules import call_module
from grass.script.raster import mapcalc as rmapcalc

options, flags = gcore.parser()
elevations = options['raster'].split(',')
years = options['years'].split(',')
level = float(options['level'])

# you have to delete old maps manualy now:
#  g.mremove rast="*rcontourevolution_*" vect="*rcontourevolution_*" -f

#def create_tmp_map_name(name):
#    return '{mod}_{pid}_{map_}_tmp'.format(mod='rcontourevolution',
#                                           pid=os.getpid(),
#                                           map_=name)


def create_tmp_map_name(name):
    return '{mod}_{map_}'.format(mod='rcontourevolution',
                                 map_=name)



contours_level_rast_stcs = []

# create contours from elevation for each year
for i, elevation in enumerate(elevations):
    # create names for temporary maps
    contours = create_tmp_map_name(elevation + '_contours')
    level_str = str(level).replace('.', '_')
    contours_level_rast_stc = create_tmp_map_name(elevation + '_contours_level_rast_stc_' + level_str)

    # now it wold be enough to just compute one level but we will
    # eventually compute multiple levels anyway
    run_command('r.contour', input=elevation, output=contours, step=2)

    run_command('v.to.rast', use='val', input=contours,
                where='level=%f' % level, value=years[i],
                output=contours_level_rast_stc)

    contours_level_rast_stcs.append(contours_level_rast_stc)

# create names for temporary maps
stc_surface_increasing_rast_contours = create_tmp_map_name('stc_surface_increasing_rast_contours')
stc_surface_increasing_elevation = create_tmp_map_name('stc_surface_increasing_elevation')
stc_surface_increasing_slope = create_tmp_map_name('stc_surface_increasing_slope')
stc_surface_increasing_aspect = create_tmp_map_name('stc_surface_increasing_aspect')
stc_surface_increasing_profile_curvature = create_tmp_map_name('stc_surface_increasing_profile_curvature')
stc_surface_increasing_tangential_curvature = create_tmp_map_name('stc_surface_increasing_tangential_curvature')
#stc_surface_decreasing_elevation = create_tmp_map_name('stc_surface_decreasing_elevation')
#stc_surface_decreasing_slope = create_tmp_map_name('stc_surface_decreasing_slope')
#stc_surface_decreasing_aspect = create_tmp_map_name('stc_surface_decreasing_aspect')
#stc_surface_decreasing_slope_inverted = create_tmp_map_name('stc_surface_decreasing_slope_inverted')
speed = create_tmp_map_name('speed')
direction = create_tmp_map_name('direction')

# patch points of the same original height (contour level) from all years together
run_command('r.patch', input=contours_level_rast_stcs,
            output=stc_surface_increasing_rast_contours)
# create a surface based on the points (in STC)
run_command('r.surf.contour', input=stc_surface_increasing_rast_contours,
            output=stc_surface_increasing_elevation)
run_command('r.slope.aspect', elevation=stc_surface_increasing_elevation,
            slope=stc_surface_increasing_slope,
            aspect=stc_surface_increasing_aspect,
            pcurvature=stc_surface_increasing_profile_curvature,
            tcurvature=stc_surface_increasing_tangential_curvature)

# patch the contours for visualization
# alternative is to compute contours on the surface but these are the contours
# which we actually want (surface can be distorted)
# and it is faster too
run_command('v.patch', input=contours_level_stcs,
            output=stc_surface_increasing_countours)

# invert surface to have time going down the hill
#rmapcalc('%s = -%s' % (stc_surface_decreasing_elevation, stc_surface_increasing_elevation))
# compute surface properties
# computing slope (surface gradient magnitude)
# and aspect (surface gradient direction projected to xy plane)
#run_command('r.slope.aspect', elevation=stc_surface_increasing_elevation,
#            slope=stc_surface_decreasing_slope,
#            aspect=stc_surface_decreasing_aspect,
#            format='degrees', precision='FCELL',
#            zfactor=1.0, min_slp_allowed=0.0)
# invert slope to have higher values where slope is lower
# to avoid negative values subtract from global max instead of 0
# using 90 as maximum slope possible
rmapcalc('eval(t = 1. / tan({slope}))\n{speed} = if(t > 15, 15, t)'.format(speed=speed,
                              slope=stc_surface_increasing_slope))

rmapcalc('eval(f = 180 + {a})\n{d} = if(f > 360, f - 360, f)'.format(d=direction, a=stc_surface_increasing_aspect))

num_elev = len(elevations)
expr_eval_values = []
expr_comp_values = []
for i in range(num_elev):
    if num_elev > i + 1:
        expr_comp = ""
        a = elevations[i]
        b = elevations[i + 1]
        r = 'rc' + a + b
        expr_comp += "{r} = xor({a} > {l}, {b} > {l})".format(a=a, b=b, l=level, r=r)
        expr_comp_values.append(expr_comp)
        expr_eval_values.append("{r}".format(r=r))

# TODO: apply mask at the beginning/before interpolation
mask = create_tmp_map_name('mask')
buffered_mask_intermediate = create_tmp_map_name('buffered_mask_intermediate')
buffered_mask = create_tmp_map_name('buffered_mask')

# r.mapcalc xor() takes only two arguments
multixor = 'if({a}, 0, {o})'.format(a=' && '.join(expr_eval_values), o=' || '.join(expr_eval_values))
expr_mask = "eval(" + ", ".join(expr_comp_values) + ")\n{m} = {mx}".format(m=mask, mx=multixor)

print expr_mask
rmapcalc(expr_mask)
run_command('r.null', map=mask, setnull=0)

# region = parse_key_val(call_module('g.region', flags='g'))

# distance = 1.5 * (float(region['nsres']) + float(region['ewres'])) / 2.

# here it would be much better to have distance in number of cells
# manual and default value adds 0.01 at the end
# this will remove small null areas (2) and then get to the old state and apply buffer (-2)
run_command('r.grow.shrink', input=mask, output=buffered_mask_intermediate, radius=2.01)
run_command('r.grow.shrink', input=buffered_mask_intermediate, output=buffered_mask, radius=-4.01)

# in GUI, add a raster flow layer:
#  d.rast.arrow map=aspect magnitude_map=slope \
#    arrow_color=black grid_color=none skip=3 scale=2

speed_masked = create_tmp_map_name('speed_masked')
direction_masked = create_tmp_map_name('direction_masked')
profile_curvature_masked = create_tmp_map_name('profile_curvature_masked')
tangential_curvature_masked = create_tmp_map_name('tangential_curvature_masked')

mask_expression = []
mask_template = '{target} = if({mask}, {source}, null())'
mask_expression.append(
    mask_template.format(
        source=speed, target=speed_masked, mask=buffered_mask))
mask_expression.append(
    mask_template.format(
        source=direction, target=direction_masked, mask=buffered_mask))
mask_expression.append(
    mask_template.format(
        source=stc_surface_increasing_profile_curvature,
        target=profile_curvature_masked, mask=buffered_mask))
mask_expression.append(
    mask_template.format(
        source=stc_surface_increasing_tangential_curvature,
        target=tangential_curvature_masked, mask=buffered_mask))

rmapcalc('\n'.join(mask_expression))

run_command('r.colors', map=speed_masked, color='sepia', flags='e')
run_command('r.colors', map=tangential_curvature_masked, rast=stc_surface_increasing_tangential_curvature)
run_command('r.colors', map=profile_curvature_masked, rast=stc_surface_increasing_profile_curvature)
