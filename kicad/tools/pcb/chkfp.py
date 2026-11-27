import pcbnew, glob, os
for f in sorted(glob.glob('ACROSS_V3.pretty/*.kicad_mod')):
    name = os.path.basename(f)[:-10]
    fp = pcbnew.FootprintLoad('ACROSS_V3.pretty', name)
    if fp is None:
        print('FAIL', name); continue
    bb = fp.GetBoundingBox(False)
    nums = sorted(set(p.GetNumber() for p in fp.Pads()))
    print(name, 'pads', len(fp.Pads()), 'bbox %.1fx%.1f' % (bb.GetWidth() / 1e6, bb.GetHeight() / 1e6), nums[:6], '...')
