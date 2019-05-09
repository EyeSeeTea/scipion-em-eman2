# coding=utf-8
# **************************************************************************
# *
# * Authors:     Adrian Quintana (adrian@eyeseetea.com) [1]
# *              Ignacio del Cano  (idelcano@eyeseetea.com) [1]
# *
# * [1] EyeSeeTea Ltd, London, UK
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 2 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
# * 02111-1307  USA
# *
# *  All comments concerning this program package may be sent to the
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************
from types import NoneType

from xmipp3.convert import writeSetOfParticles

import pyworkflow.protocol.params as params
import pyworkflow.em as pwem

from tomo.protocols import ProtTomoBase
from pyworkflow.protocol import STEPS_PARALLEL, join
from pprint import pprint
import eman2
from eman2.constants import *

from tomo.objects import SetOfSubTomograms, SubTomogram

SAME_AS_PICKING = 0
class EmanProtTomoRefinement(pwem.EMProtocol, ProtTomoBase):
    """Protocol to performs a conventional iterative subtomogram averaging using the full set of particles."""
    _outputClassName = 'SubTomogramRefinement'
    _label = 'subtomogram refinement'

    def __init__(self, **kwargs):
        pwem.EMProtocol.__init__(self, **kwargs)
        self.stepsExecutionMode = STEPS_PARALLEL

    #--------------- DEFINE param functions ---------------

    def _defineParams(self, form):
        form.addSection(label='Params')
        form.addParam('inputSetOfSubTomogram', params.PointerParam,
                      pointerClass='SetOfSubTomograms',
                      important=True, label='Input SetOfSubTomograms',
                      help='Select the SetOfSubTomograms.')
        form.addParam('inputRef', params.PointerParam,
                      pointerClass='Volume',
                      default=None, label='Input Ref Tomogram',
                      help='3D reference for initial model generation.'
                           'No reference is used by default.')

        group = form.addGroup('Config')
        group.addParam('niter', pwem.IntParam, default=5,
                       label='Number of iterations',
                       help='The number of iterations to perform.')
        group.addParam('mass', pwem.FloatParam, default=500.0,
                       label='Mass:',
                       help='Default=500.0.'
                            'mass')
        group.addParam('threads', pwem.IntParam, default=2,
                       label='Threads:',
                       help='Number of threads')
        group.addParam('pkeep', pwem.FloatParam, default=0.8,
                       label='Particle keep:',
                       help='Fraction of particles to keep')
        group.addParam('goldstandard', pwem.IntParam, default=-1,
                       label='GoldStandard:',
                       help='initial resolution for gold standard refinement')
        group.addParam('goldcontinue', params.BooleanParam, default=False,
                       label='Gold continue',
                       help='continue from an existing gold standard refinement')
        group.addParam('maskFile', params.PointerParam, allowsNull=True,
                       pointerClass='VolumeMask', label='Mask file',
                       help='Select the mask object')
        group.addParam('setsf', params.PointerParam, allowsNull=True,
                       pointerClass='VolumeMask', label='Structure factor',
                       help='Select the structure factor')
        group.addParam('sym', params.StringParam, default='c1',
                       label='Symmetry',
                      help='Symmetry (Default: c1')
        group.addParam('localfilter', params.BooleanParam, default=False,
                       label='Local filter',
                      help='use tophat local')
        group.addParam('maxtilt', params.FloatParam, default=90.0,
                       label='maxtilt',
                       help='Explicitly zeroes data beyond specified tilt angle.'
                            'Assumes tilt axis exactly on Y and zero tilt in X-Y'
                            'plane. Default 90 (no limit).')

        form.addParallelSection(threads=2, mpi=4)

    #--------------- INSERT steps functions ----------------


    def _insertAllSteps(self):
        #TODO: Get the basename.hdf from the inputSetOfSubTomogram
        #self._insertFunctionStep('convertInputStep')
        print('#--------------- convertInputStep -----------------------')
        self._insertFunctionStep('refinementSubtomogram')
        #TODO: Set and show the output
        #self._insertFunctionStep('createOutputStep')

    #--------------- STEPS functions -----------------------
    def refinementSubtomogram(self):
        """ Run the Subtomogram refinement. """
        input = pwem.os.getcwd() + "/" + self.inputSetOfSubTomogram.get().getFileName().replace("subtomograms.sqlite","extra/sptboxer_01/basename.hdf")
        print('#--------------- refinementSubtomogram ----------------------- %s ' % input)
        args = ' %s' % input
        if not isinstance(self.inputRef.get(), NoneType):
            args += (' --reference=%s ' % self.inputRef.get().getFileName())
        args += (' --mass=%f' % self.mass)
        args += ' --threads=%d' % self.threads
        args += ' --goldstandard=%d ' % self.goldstandard
        args += ' --pkeep=%f ' % self.pkeep
        args += ' --sym=%s ' % self.sym
        args += ' --maxtilt=%s ' % self.maxtilt
        if self.niter > 1:
            args += ' --niter=%d' % self.niter
        if self.goldcontinue:
            args += ' --goldcontinue '
        if self.localfilter:
            args += ' --localfilter '
        print('#--------------- STEPS functions -----------------------')
        print("command: e2spt_refine.py " + args)
        print('#--------------- STEPS functions -----------------------')
        program = eman2.Plugin.getProgram('e2spt_refine.py')
        self.runJob(program, args,
                    cwd=self._getExtraPath())

    def runMLStep(self, params):
        pass

    def createOutputStep(self):
        pass
#
    #--------------- INFO functions -------------------------

    def _validate(self):
        errors = []

        if not eman2.Plugin.isNewVersion():
            errors.append('Your EMAN2 version does not support the subtomogram refinement. '
                          'Please update your installation to EMAN 2.23 or newer.')

        return errors

    def _citations(self):
        return []

    def _summary(self):
        summary = []
        summary.append("SetOfSubTomograms source: %s" % (self.inputSetOfSubTomogram.get().getFileName()))

        if not isinstance(self.inputRef.get(), NoneType):
            summary.append("Referenced Tomograms source: %s" % (self.inputRef.get().getFileName()))

        if self.getOutputsSize() >= 1:
            summary.append("Subtomogram Averaging Completed")
        else:
            summary.append("Subtomogram Averaging not ready yet.")

        return summary

    def _methods(self):
        return []