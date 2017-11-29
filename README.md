# Dogbone

A Fusion360 addin that creates dogbone joints for wood joinery.


## Changes

This version has been significantly optimized as follows:
- Instead of generating one plane, sketch, and sweep cut for each dogbone, it groups the dogbones by their vertical
  extents and produces the minimum number of features in the history tree as possible.
- Introduced "Output Unconstrained Geometry" option to directly compute the locations of dogbone circle in the sketch,
  producing the minimum amount of sketch geometry possible. This led to a >5x speedup of generating each dogbone.

The net result is that, for my use case, I can generate 208 fillets in 28 objects in 73 sec. Since they are all lying
in the same plane, it only generates three history operations (plane, sketch, extrusion). Previously this would take
forever, freeze the UI, and generate 600+ operations in the history.

Note: The bulk of the time is because every call to the Fusion API (adding geometry, extrusions, etc.) is extremely
slow.

Additionally, other enhancements were added:
- Progress bar shows current status.
- The operation can be canceled midway (use Undo to delete the partial geometry created).
- Saves the last parameters used (cleared on relaunch of Fusion)
- Skips non-vertical edges selected.
- Benchmarking
- Code is refactored into object-oriented fashion to be more manageable, and utility functions split out.
- Robustness: Exception handling is consolidated, tracebacks always shown, launching the plugin automatically cleans up
  old crashed instances of the plugin.

New enhancements by DVE2000:
- Add options to create dogbones along the longest side or shortest side of a mortise. This is useful when using non-through
  mortises and you'd like the required holes to be hidden by the tenon. Or even just for looks.
- Add option to try create a minimal Dogbone. See http://fablab.ruc.dk/more-elegant-cnc-dogbones/

## Limitations


Still TODO:
- Handle acute angles (<90deg) by generating a slot.
- Allow user to specify orientation (i.e. select "vertical" vector) instead of only handling edges.
- Handle duplicate edges (avoid generating duplicate overlapping geometry)
- Even if you use the slower "constrained" version, once the initial sketch is modified, the dogbones will not be 
  recreated properly. Just add the dogbones last, or delete them before changing the underlying sketch and redo them afterwards.
  I need to figure out the appropriate constraints...

## Usage:

First see [How to install sample Add-Ins and Scripts](https://rawgit.com/AutodeskFusion360/AutodeskFusion360.github.io/master/Installation.html)

See a youtube video of using this app here:
http://youtu.be/EM13Dz4Mqnc

Select edges interior to 90 degree angles. Specify a tool diameter and a radial offset.
The add-in will then create a dogbone with diamater equal to the tool diameter plus
twice the offset (as the offset is applied to the radius) at each selected edge.
Alternatively, select an entire body and the add-in will automatically apply a dog-bone to all interior vertical edges.


## License

Samples are licensed under the terms of the [MIT License](http://opensource.org/licenses/MIT). Please see the [LICENSE](LICENSE) file for full details.


## Written by

- Original version by Casey Rogers: http://github.com/caseycrogers/Dogbone
- Modified by Patrick Rainsberry (Autodesk Fusion 360 Business Development)
- Modified by David Liu (http://github.com/iceboundflame/)
- Modified by DVE2000: http://github.com/DVE2000/Dogbone
