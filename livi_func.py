# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

from vi_func import progressfile, progressbar, retpmap, logentry
from subprocess import Popen, PIPE
import os, datetime

pmaperrdict = {'fatal - too many prepasses, no global photons stored\n': "Too many prepasses have occurred. Make sure light sources can see your geometry",
               'fatal - too many prepasses, no global photons stored, no caustic photons stored\n': "Too many prepasses have occurred. Turn off caustic photons and encompass the scene",
               'fatal - zero flux from light sources\n': "No light flux, make sure there is a light source and that photon port normals point inwards",
               'fatal - no light sources in distribPhotons\n': "No light sources. Photon mapping does not work with HDR skies",
               'fatal - no valid photon ports found\n': 'Re-export the geometry',
               'fatal - failed photon distribution\n': "Failed photon distribution"}

class rvu():
    def __init__(self, op):
        self.op = op

    def run(self):
        if self.op.simnode.pmap:
            self.runpmap()
        else:
            self.runrvu()

    def runpmap(self):
        self.pmap = pmap(self.op)

    def poll(self):
        if self.pmap.poll():
            return 'Running Pmap'
        if self.rvu.poll():
            return 'Running Rvu'
        else:
            return 'Finished'






class rpict():
    def __init__(op):
        pass
    def run(op):
        pass

class pmap():
    def __init__(self, op):
        self.op = op

    def poll(self):
        if self.pmrun.poll() is None:
            with open('{}.pmapmon'.format(self.op.scene['viparams']['filebase']), 'r') as vip:
                for line in vip.readlines()[::-1]:
                    if '%' in line:
                        curres = float(line.split()[6][:-2])
                        break

            if self.pfile.check(curres) == 'CANCELLED':
                self.pmrun.kill()
                return ('CANCELLED')

        else:
            return ('FINISHED')

        if self.kivyrun.poll() is None:
            self.kivyrun.kill()

        with open('{}.pmapmon'.format(self.op.scene['viparams']['filebase']), 'r') as pmapfile:
            for line in pmapfile.readlines():
                if line in pmaperrdict:
                    logentry('ERROR', pmaperrdict[line])
                    return ('ERROR', 'Check log')

    def run(self, op):
        self.pfile = progressfile(op.scene, datetime.datetime.now(), 100)
        self.kivyrun = progressbar(os.path.join(op.scene['viparams']['newdir'], 'viprogress'))

        amentry, pportentry, cpentry, cpfileentry = retpmap(op.simnode, op.frame, op.scene)
        open('{}.pmapmon'.format(op.scene['viparams']['filebase']), 'w')
        pmcmd = 'mkpmap -t 20 -e {1}.pmapmon -fo+ -bv+ -apD 0.001 {0} -apg {1}-{2}.gpm {3} {4} {5} {1}-{2}.oct'.format(pportentry, op.scene['viparams']['filebase'], op.frame, op.simnode.pmapgno, cpentry, amentry)
        print(pmcmd)
        self.pmrun = Popen(pmcmd.split(), stderr = PIPE, stdout = PIPE)

    def terninate(self):
        pass
