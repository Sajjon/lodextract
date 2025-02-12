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


# http://aethra-cronicles-remake.googlecode.com/svn-history/r4/trunk/export/sergroj/RSDef.pas
# vcmi/client/CAnimation.cpp

import struct
from io import RawIOBase

from PIL import Image, ImageDraw
from collections import defaultdict
import os
import json
import numpy as np

import hashlib

class Block:

    def __init__(self, frameNames, offsets):
        assert(len(frameNames) == len(offsets))
        all(isinstance(n, str) for n in frameNames)
        self.frameNames = frameNames
        all(isinstance(n, int) for n in offsets)
        self.offsets = offsets
        self.frameCount = len(frameNames)

# class Frame:
#
#     def __init__(self, name: str):
#         self.name = name
#         self.offset = None
#
#     def setOffset(self, offset: int):
#         self.offset = offset


def sha256(data):
    return hashlib.sha256(data).hexdigest()

def extract_def(infile):
    f = open(infile)
    deffilename = os.path.basename(infile)
    bn = os.path.splitext(deffilename)[0].lower()
    outdir = "/Users/sajjon/Library/Application Support/Makt/Temp/def_file_entries_from_H3sprite_lod/"
    extract_def_stream(f, deffilename, outdir)

def extract_def_stream(stream: RawIOBase, deffilename: str, outdir: str):
    bn = deffilename
    f = stream

    outpath = os.path.join(outdir,deffilename)
    if os.path.exists(outpath):
        if not os.path.isdir(outpath):
            print("output path exists and is no directory")
            return False
    else:
        os.mkdir(outpath)


    # t - type
    # blocks - # of blocks
    # the second and third entry are width and height which are not used
    t,_,_,blockCount = struct.unpack("<IIII", f.read(16))

    palette = []
    for i in range(256):
        r,g,b = struct.unpack("<BBB", f.read(3))
        palette.extend((r,g,b))

    blocksByID = defaultdict()
    for blockIndex in range(blockCount):
        # entries - number of images in this block
        # the third and fourth entry have unknown meaning
        blockId,frameCount,_,_ = struct.unpack("<IIII", f.read(16))
        frameNames=[]
        # a list of 13 character long filenames
        for frameIndex in range(frameCount):
            frameNameRaw, = struct.unpack("13s", f.read(13))
            frameName = frameNameRaw.decode('utf8')
            frameNameNonNull = frameName
            if '\x00' in frameName:
                frameNameNonNull = frameName.strip().strip('\x00')
            frameNames.append(frameNameNonNull)

        # a list of offsets
        offsetList=[]
        for frameIndex in range(frameCount):
            frameOffset, = struct.unpack("<I", f.read(4))
            offsetList.append(frameOffset)


        blocksByID[blockId] = Block(frameNames, offsetList)

    out_json = {"sequences":[],"type":t,"format":-1}
    out_hashes_json = { "defFileName": deffilename, "hashesOfFrames": []  }

    firstfw,firstfh = -1,-1
    globalFrameId = -1

    for blockid,block in blocksByID.items():
        bid = blockid
        frames=[]
        for frameid in range(block.frameCount):
            globalFrameId += 1
            j = frameid
            frameOffset = block.offsets[frameid]
            framename = block.frameNames[frameid]
            f.seek(frameOffset)
            pixeldata = b""
            # first entry is the size which is unused
            # fmt - encoding format of image data
            # fw,fh - full width and height
            # w,h - width and height, w must be a multiple of 16
            # lm,tm - left and top margin
            _,fmt,fw,fh,w,h,lm,tm = struct.unpack("<IIIIIIii", f.read(32))

            outname = os.path.join(
                outdir,
                deffilename,
                "%s.png" % framename
            )

            out_hash_json = {"frameName": framename, "globalFrameId": globalFrameId, "blockId": blockid, "frameIdInBlock": frameid, "hash": "not_set"}

            # SGTWMTA.def and SGTWMTB.def fail here
            # they have inconsistent left and top margins
            # they seem to be unused
            if lm > fw or tm > fh:
                print("margins (%dx%d) are higher than dimensions (%dx%d)"%(lm,tm,fw,fh))
                return False

            if firstfw==-1 and firstfh == -1:
                firstfw = fw
                firstfh = fh
            else:
                if firstfw > fw:
                    print("must enlarge width")
                    fw = firstfw
                if firstfw < fw:
                    print("first with smaller than latter one")
                    return False
                if firstfh > fh:
                    print("must enlarge height")
                    fh = firstfh
                if firstfh < fh:
                    print("first height smaller than latter one")
                    return False

            if out_json["format"] == -1:
                out_json["format"] = fmt
            elif out_json["format"] != fmt:
                print("format %d of this frame does not match of last frame %d"%(fmt,global_fmt))
                return False

            frames.append(os.path.join("%s.dir"%bn,"%02d_%02d.png"%(bid,j)))

            if w != 0 and h != 0:
                if fmt == 0:
                    pixeldata = f.read(w*h)
                elif fmt == 1:
                    lineoffs = struct.unpack("<"+"I"*h, f.read(4*h))
                    for lineoff in lineoffs:
                        f.seek(frameOffset+32+lineoff)
                        totalrowlength=0
                        while totalrowlength<w:
                            code,length = struct.unpack("<BB", f.read(2))
                            length+=1
                            if code == 0xff: #raw data
                                pixeldata += f.read(length)
                            else: # rle
                                pixeldata += length*chr(code)
                            totalrowlength+=length
                elif fmt == 2:
                    lineoffs = struct.unpack("<%dH"%h, f.read(2*h))
                    _,_ = struct.unpack("<BB", f.read(2)) # unknown
                    for lineoff in lineoffs:
                        if f.tell() != frameOffset+32+lineoff:
                            # print("unexpected offset: %d, expected %d"%(f.tell(),frameOffset+32+lineoff))
                            f.seek(frameOffset+32+lineoff)
                        totalrowlength=0
                        while totalrowlength<w:
                            segment, = struct.unpack("<B", f.read(1))
                            code = segment>>5
                            length = (segment&0x1f)+1
                            if code == 7: # raw data
                                pixeldata += f.read(length)
                            else: # rle
                                pixeldata += (length*chr(code)).encode('utf8')
                            totalrowlength+=length
                elif fmt == 3:
                    # each row is split into 32 byte long blocks which are individually encoded
                    # two bytes store the offset for each block per line 
                    lineoffs = [struct.unpack("<"+"H"*(w/32), f.read(w/16)) for i in range(h)]

                    for lineoff in lineoffs:
                        for i in lineoff:
                            if f.tell() != frameOffset+32+i:
                                # print("unexpected offset: %d, expected %d"%(f.tell(),frameOffset+32+i))
                                f.seek(frameOffset+32+i)
                            totalblocklength=0
                            while totalblocklength<32:
                                segment, = struct.unpack("<B", f.read(1))
                                code = segment>>5
                                length = (segment&0x1f)+1
                                if code == 7: # raw data
                                    pixeldata += f.read(length)
                                else: # rle
                                    pixeldata += length*chr(code)
                                totalblocklength+=length
                else:
                    print("unknown format: %d"%fmt)
                    return False

                imp = Image.frombytes('P', (w,h),pixeldata) # PIL.Image.frombuffer(mode, size, data, decoder_name='raw', *args)[source]

                imp.putpalette(palette)
                # convert to RGBA
                imrgb = imp.convert("RGBA")
                # replace special colors
                # 0 -> (0,0,0,0)    = full transparency
                # 1 -> (0,0,0,0x40) = shadow border
                # 2 -> ???
                # 3 -> ???
                # 4 -> (0,0,0,0x80) = shadow body
                # 5 -> (0,0,0,0)    = selection highlight, treat as full transparency
                # 6 -> (0,0,0,0x80) = shadow body below selection, treat as shadow body
                # 7 -> (0,0,0,0x40) = shadow border below selection, treat as shadow border
                pixrgb = np.array(imrgb)
                pixp = np.array(imp)
                pixrgb[pixp == 0] = (0,0,0,0)
                pixrgb[pixp == 1] = (0,0,0,0x40)
                pixrgb[pixp == 4] = (0,0,0,0x80)
                pixrgb[pixp == 5] = (0,0,0,0)
                pixrgb[pixp == 6] = (0,0,0,0x80)
                pixrgb[pixp == 7] = (0,0,0,0x40)
                imrgb = Image.fromarray(pixrgb)
                im = Image.new('RGBA', (fw,fh), (0,0,0,0))
                im.paste(imrgb,(lm,tm))
            else: # either width or height is zero
                im = Image.new('RGBA', (fw,fh), (0,0,0,0))
            im.save(outname)

            pixeldata_sha256 = sha256(pixeldata)
            out_hash_json["hash"] = pixeldata_sha256
            out_hashes_json["hashesOfFrames"].append(out_hash_json)
        out_json["sequences"].append({"group":bid,"frames":frames})
        with open(os.path.join(outdir,"%s.json"%bn),"w+") as o:
            json.dump(out_json,o,indent=4)
        with open(os.path.join(outdir, "%s_outhash.json"%deffilename), "w+") as o:
            json.dump(out_hashes_json, o, indent=4)
    return out_hashes_json

if __name__ == '__main__':
    import sys
    # if len(sys.argv) != 3:
    #     print "usage: %s input.def ./outdir"%sys.argv[0]
    #     print "to process all files:"
    #     print "    for f in *.def; do n=`basename $f .def`; mkdir -p defs/$n; %s defextract.py $f defs/$n; done"%sys.argv[0]
    #     exit(1)
    # ret = extract_def(sys.argv[1], sys.argv[2])
    infile = "/Users/sajjon/Library/Application Support/Makt/Data/H3sprite.lod"
    print("WARNING hardcoded to extract def files in lod %s" % infile)

    ret = extract_def(infile)
    exit(0 if ret else 1)
