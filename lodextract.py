#!/usr/bin/env python
#
# Copyright (C) 2014  Johannes Schauer <j.schauer@email.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import zlib
import struct
import os
import json
from PIL import Image, ImageDraw

from defextract import extract_def_stream


def is_pcx(data):
    size,width,height = struct.unpack("<III",data[:12])
    return size == width*height or size == width*height*3

def read_pcx(data):
    size,width,height = struct.unpack("<III",data[:12])
    if size == width*height:
        im = Image.fromstring('P', (width,height),data[12:12+width*height])
        palette = []
        for i in range(256):
            offset=12+width*height+i*3
            r,g,b = struct.unpack("<BBB",data[offset:offset+3])
            palette.extend((r,g,b))
        im.putpalette(palette)
        return im
    elif size == width*height*3:
        return Image.fromstring('RGB', (width,height),data[12:])
    else:
        return None

def unpack_lod(infile,outdir, outdirOfHashesFile: str, defFilesOfInterest):
    all(isinstance(n, str) for n in defFilesOfInterest)
    f = open(infile, 'rb')
    archiveFileName = os.path.basename(infile)
    print("f.name='%s'" % f.name)
    header = f.read(4)
    if not header.startswith(b'LOD'):
        print("not LOD file: '%s'"%header)
        return False

    f.seek(8)
    total, = struct.unpack("<I", f.read(4))
    f.seek(92)

    files=[]
    for i in range(total):
        filename, = struct.unpack("16s", f.read(16))
        filename = str(filename[:filename.index(b'\0')], 'utf8') # .lower()
        offset,size,_,csize = struct.unpack("<IIII", f.read(16))
        files.append((filename,offset,size,csize))


    out_json = {"archive": archiveFileName, "hashesOfDefFiles": []}

    for filename,offset,size,csize in files:
        deffilename = filename
        filename=os.path.join(outdir,filename)
        # print(filename)
        # print("type of variable 'filename' is: '%s'" % (type(filename)))
        # exit(1)
        f.seek(offset)
        if csize != 0:
            data = zlib.decompress(f.read(csize))
        else:
            data = f.read(size)
        if is_pcx(data):
            im = read_pcx(data)
            if not im:
                return False
            filename = os.path.splitext(filename)[0]
            filename = filename+".png"
            im.save(filename)
        else:
            with open(filename,"wb+") as o:
                o.write(data)

            lowers = defFilesOfInterest
            for i in range(len(lowers)):
                lowers[i] = lowers[i].lower()

            if deffilename.lower() in lowers:
                print("Found def file of interest: '%s'" % deffilename)
                with open(filename, "rb") as df:
                    hashes_json_of_def_file = extract_def_stream(df, deffilename, "/Users/sajjon/Library/Application Support/Makt/Temp/def_file_entries_from_H3sprite_lod/")
                    out_json["hashesOfDefFiles"].append(hashes_json_of_def_file)

    with open(os.path.join(outdirOfHashesFile, "%s_hashes_of_def_files.json" % archiveFileName), "w+") as o:
        json.dump(out_json, o, indent=4)

    return True

if __name__ == '__main__':
    # import sys
    # if len(sys.argv) != 3:
    #     print "usage: %s infile.lod ./outdir"%sys.argv[0]
    #     print ""
    #     print "usually after installing the normal way:"
    #     print "    %s .vcmi/Data/H3bitmap.lod .vcmi/Mods/vcmi/Data/"%sys.argv[0]
    #     print "    rm .vcmi/Data/H3bitmap.lod"
    #     print "    %s .vcmi/Data/H3sprite.lod .vcmi/Mods/vcmi/Data/"%sys.argv[0]
    #     print "    rm .vcmi/Data/H3sprite.lod"
    #     exit(1)
    # ret = unpack_lod(sys.argv[1], sys.argv[2])

    infile = "/Users/sajjon/Library/Application Support/Makt/Data/H3sprite.lod"
    outdir = "/Users/sajjon/Library/Application Support/Makt/Temp/def__files_from__H3sprite_lod/"
    outdirOfHashesFile = "/Users/sajjon/Library/Application Support/Makt/Temp/hashesOfDefFilesInArchive/"
    print("WARNING hardcoded to extract def files in lod at path\n'%s'\nto path: %s" % (infile, outdir))

    defFilesOfInterest = [
        # Ground terrain
        "DIRTTL.def",
        "SANDTL.def",
        "GRASTL.def",
        "Snowtl.def",
        "SWMPTL.def",
        "ROUGTL.def",
        "SUBBTL.def",
        "LAVATL.def",
        "WATRTL.def",
        "ROCKTL.def",

        # Road
        "dirtrd.def",
        "gravrd.def",
        "cobbrd.def",

        # River
        "Clrrvr.def",
        "Icyrvr.def",
        "Mudrvr.def",
        "Lavrvr.def",
    ]

    ret = unpack_lod(infile, outdir, outdirOfHashesFile, defFilesOfInterest)
    if ret:
        print("Successfully extracted LOD archive")
    else:
        print("Failed to extract LOD archive")
    exit(0 if ret else 1)
