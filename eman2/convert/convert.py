# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (delarosatrevin@scilifelab.se) [1]
# *              Laura del Cano (ldelcano@cnb.csic.es) [1]
# *              Josue Gomez Blanco (josue.gomez-blanco@mcgill.ca) [1]
# *              Grigory Sharov (gsharov@mrc-lmb.cam.ac.uk) [2]
# *
# * [1] Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# * [2] MRC Laboratory of Molecular Biology (MRC-LMB)
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 3 of the License, or
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

import glob
import itertools
import json
import numpy
import os
from io import open

import pwem.constants as emcts
import pyworkflow.utils as pwutils
from pwem.objects.data import Coordinate, Particle, Transform
from pyworkflow.object import Float
from pwem.emlib.image import ImageHandler
import pwem.emlib.metadata as md

from eman2.constants import TOMO_NEEDED_MSG
from .. import Plugin


def loadJson(jsonFn):
    """ This function loads the Json dictionary into memory """
    jsonFile = open(jsonFn)
    jsonDict = json.load(jsonFile)
    jsonFile.close()
    return jsonDict


def writeJson(jsonDict, jsonFn):
    """ This function write a Json dictionary """
    with open(jsonFn, 'w') as outfile:
        json.dump(jsonDict, outfile)


def readCTFModel(ctfModel, filename):
    jsonDict = loadJson(filename)
    keyPos = None
    ctfPhaseShift = 0.0

    if 'ctf_frame' in jsonDict:
        keyPos = jsonDict['ctf_frame'][1]
    elif 'ctf' in jsonDict:
        keyPos = jsonDict['ctf'][0]
    else:
        setWrongDefocus(ctfModel)

    if keyPos:
        defocus = float(keyPos['defocus'])
        defocusAngle = float(keyPos['dfang'])
        dfdiff = float(keyPos['dfdiff'])
        ampcont = float(keyPos['ampcont'])
        defocusU = 10000.0 * defocus + 5000.0 * dfdiff
        defocusV = 20000.0 * defocus - defocusU
        ctfPhaseShift = calculatePhaseShift(ampcont)

        ctfModel.setStandardDefocus(defocusU, defocusV, defocusAngle)
        if 'ctf_im2d' in jsonDict:
            # psdFile = jsonDict['ctf_im2d']['__image__'][0]
            fnBase = pwutils.removeExt(filename) + '_jsonimg'
            psdFile = "1@%s.hdf" % fnBase
            if pwutils.exists(psdFile):
                ctfModel.setPsdFile(psdFile)
    ctfModel.setPhaseShift(float(ctfPhaseShift))


def setWrongDefocus(ctfModel):
    ctfModel.setDefocusU(-999)
    ctfModel.setDefocusV(-1)
    ctfModel.setDefocusAngle(-999)


def writeCTFModel(ctfObj, filename):
    """ Write a CTFModel object as Xmipp .ctfparam"""
    pass


def jsonToCtfModel(ctfJsonFn, ctfModel):
    """ Create a CTFModel from a json file """
    mdFn = str(ctfJsonFn).replace('particles', 'info')
    mdFn = mdFn.split('__ctf_flip')[0] + '_info.json'
    if pwutils.exists(mdFn):
        readCTFModel(ctfModel, mdFn)


def readSetOfCoordinates(workDir, micSet, coordSet, invertY=False, newBoxer=False):
    """ Read from Eman .json files.
    Params:
        workDir: where the Eman boxer output files are located.
        micSet: the SetOfMicrographs to associate the .json, which
            name should be the same of the micrographs.
        coordSet: the SetOfCoordinates that will be populated.
    """
    if newBoxer:
        # read boxSize from info/project.json
        jsonFnbase = pwutils.join(workDir, 'info', 'project.json')
        jsonBoxDict = loadJson(jsonFnbase)
        size = int(jsonBoxDict["global.boxsize"])
    else:
        # read boxSize from e2boxercache/base.json
        jsonFnbase = pwutils.join(workDir, 'e2boxercache', 'base.json')
        jsonBoxDict = loadJson(jsonFnbase)
        size = int(jsonBoxDict["box_size"])

    jsonFninfo = pwutils.join(workDir, 'info/')

    for mic in micSet:
        micBase = pwutils.removeBaseExt(mic.getFileName())
        micPosFn = ''.join(glob.glob(jsonFninfo + '*' + micBase + '_info.json'))
        readCoordinates(mic, micPosFn, coordSet, invertY)
    coordSet.setBoxSize(size)

def readSetOfCoordinates3D(jsonBoxDict, coord3DSetDict, inputTomo, updateItem=None):
    if jsonBoxDict.has_key("boxes_3d"):
        boxes = jsonBoxDict["boxes_3d"]

        for box in boxes:
            classKey = box[5]
            coord3DSet = coord3DSetDict[classKey]
            coord3DSet.enableAppend()

            newCoord = readCoordinate3D(box, inputTomo)

            # Execute Callback
            if updateItem: updateItem(newCoord)

            coord3DSet.append(newCoord)


def readCoordinates(mic, fileName, coordsSet, invertY=False):
    if pwutils.exists(fileName):
        jsonPosDict = loadJson(fileName)

        if "boxes" in jsonPosDict:
            boxes = jsonPosDict["boxes"]

            for box in boxes:
                x, y = box[:2]

                if invertY:
                    y = mic.getYDim() - y

                coord = Coordinate()
                coord.setPosition(x, y)
                coord.setMicrograph(mic)
                coordsSet.append(coord)

def readCoordinate3D(box, inputTomo):
    from pwem import Domain
    Coordinate3D = Domain.importFromPlugin("tomo.objects", "Coordinate3D", errorMsg=TOMO_NEEDED_MSG)
    x, y, z = box[:3]
    coord = Coordinate3D()
    coord.setPosition(x, y, z)
    coord.setVolume(inputTomo)
    return coord

def writeSetOfSubTomograms(micSet, filename):
    writeSetOfParticles(micSet, filename)

def writeSetOfMicrographs(micSet, filename):
    """ Simplified function borrowed from xmipp. """
    mdata = md.MetaData()

    for img in micSet:
        objId = mdata.addObject()
        imgRow = md.Row()
        imgRow.setValue(md.MDL_ITEM_ID, objId)

        index, fname = img.getLocation()
        fn = ImageHandler.locationToXmipp((index, fname))
        imgRow.setValue(md.MDL_MICROGRAPH, fn)

        if img.isEnabled():
            enabled = 1
        else:
            enabled = -1
        imgRow.setValue(md.MDL_ENABLED, enabled)
        imgRow.writeToMd(mdata, objId)

    mdata.write('Micrographs@%s' % filename)


def readSetOfParticles(lstFile, partSet, copyOrLink, direc):
    for index, fn in iterLstFile(lstFile):
        item = Particle()
        # set full path to particles stack file
        abspath = os.path.abspath(lstFile)
        fn = abspath.replace('sets/%s' % os.path.basename(lstFile), '') + fn
        newFn = pwutils.join(direc, os.path.basename(fn))
        if not pwutils.exists(newFn):
            copyOrLink(fn, newFn)

        item.setLocation(index, newFn)
        partSet.append(item)


def writeSetOfParticles(partSet, path, **kwargs):
    """ Convert the imgSet particles to .hdf files as expected by Eman.
    This function should be called from a current dir where
    the images in the set are available.
    """
    ext = pwutils.getExt(partSet.getFirstItem().getFileName())[1:]
    if ext == 'hdf':
        # create links if input has hdf format
        for fn in partSet.getFiles():
            newFn = pwutils.removeBaseExt(fn).split('__ctf')[0] + '.hdf'
            newFn = pwutils.join(path, newFn)
            pwutils.createLink(fn, newFn)
            print("   %s -> %s" % (fn, newFn))
    else:
        firstCoord = partSet.getFirstItem().getCoordinate() or None
        hasMicName = False
        if firstCoord:
            hasMicName = firstCoord.getMicName() or False

        fileName = ""
        a = 0
        proc = Plugin.createEmanProcess(args='write')

        for i, part in iterParticlesByMic(partSet):
            micName = micId = part.getMicId()
            if hasMicName:
                micName = pwutils.removeBaseExt(part.getCoordinate().getMicName())
            objDict = part.getObjDict()

            if not micId:
                micId = 0

            suffix = kwargs.get('suffix', '')
            if hasMicName and (micName != str(micId)):
                objDict['hdfFn'] = pwutils.join(path,
                                                "%s%s.hdf" % (micName, suffix))
            else:
                objDict['hdfFn'] = pwutils.join(path,
                                                "mic_%06d%s.hdf" % (micId, suffix))

            alignType = kwargs.get('alignType')

            if alignType != emcts.ALIGN_NONE:
                shift, angles = alignmentToRow(part.getTransform(), alignType)
                # json cannot encode arrays so I convert them to lists
                # json fail if has -0 as value
                objDict['_shifts'] = shift.tolist()
                objDict['_angles'] = angles.tolist()
            objDict['_itemId'] = part.getObjId()

            # the index in EMAN begins with 0
            if fileName != objDict['_filename']:
                fileName = objDict['_filename']
                if objDict['_index'] == 0:
                    a = 0
                else:
                    a = 1
            objDict['_index'] = int(objDict['_index'] - a)
            # Write the e2converter.py process from where to read the image
            print(json.dumps(objDict), file=proc.stdin, flush=True)
            proc.stdout.readline()
        proc.kill()


def getImageDimensions(imageFile):
    """ This function will allow us to use EMAN2 to read some formats
     not currently supported by the native image library (Xmipp).
     Underneath, it will call a script to do the job.
    """
    proc = Plugin.createEmanProcess('e2ih.py', args=imageFile)
    return tuple(map(int, proc.stdout.readline().split()))


def convertImage(inputLoc, outputLoc):
    """ This function will allow us to use EMAN2 to write some formats
     not currently supported by the native image library (Xmipp).
     Underneath, it will call an script to do the job.
    """

    def _getFn(loc):
        """ Use similar naming convention as in Xmipp.
        This does not works for EMAN out of here.
        """
        if isinstance(loc, tuple):
            if loc[0] != emcts.NO_INDEX:
                return "%06d@%s" % loc
            return loc[1]
        else:
            return loc

    proc = Plugin.createEmanProcess('e2ih.py', args='%s %s' % (_getFn(inputLoc),
                                                            _getFn(outputLoc)))
    proc.wait()


def iterLstFile(filename):
    f = open(filename)
    for line in f:
        if '#' not in line:
            # Decompose Eman filename
            index, filename = int(line.split()[0]) + 1, line.split()[1]
            yield index, filename
    f.close()


def geometryFromMatrix(matrix, inverseTransform):
    from pwem.convert.transformations import translation_from_matrix, euler_from_matrix
    if inverseTransform:
        from numpy.linalg import inv
        matrix = inv(matrix)
        shifts = -translation_from_matrix(matrix)
    else:
        shifts = translation_from_matrix(matrix)
    angles = -numpy.rad2deg(euler_from_matrix(matrix, axes='szyz'))
    return shifts, angles


def matrixFromGeometry(shifts, angles, inverseTransform):
    """ Create the transformation matrix from a given
    2D shifts in X and Y...and the 3 euler angles.
    """
    from pwem.convert.transformations import euler_matrix
    from numpy import deg2rad
    radAngles = -deg2rad(angles)

    M = euler_matrix(radAngles[0], radAngles[1], radAngles[2], 'szyz')
    if inverseTransform:
        from numpy.linalg import inv
        M[:3, 3] = -shifts[:3]
        M = inv(M)
    else:
        M[:3, 3] = shifts[:3]

    return M


def alignmentToRow(alignment, alignType):
    """
    is2D == True-> matrix is 2D (2D images alignment)
            otherwise matrix is 3D (3D volume alignment or projection)
    invTransform == True  -> for xmipp implies projection
                          -> for xmipp implies alignment
    """
    #     is2D = alignType == em.ALIGN_2D
    #     inverseTransform = alignType == em.ALIGN_PROJ

    # transformation matrix is processed here because
    # it uses routines available through scipion python
    matrix = alignment.getMatrix()
    return geometryFromMatrix(matrix, True)


def rowToAlignment(alignmentList, alignType):
    """
    is2D == True-> matrix is 2D (2D images alignment)
            otherwise matrix is 3D (3D volume alignment or projection)
    invTransform == True  -> for xmipp implies projection
        """
    # use all angles in 2D since we might have mirrors
    # is2D = alignType == em.ALIGN_2D
    inverseTransform = alignType == emcts.ALIGN_PROJ

    alignment = Transform()
    angles = numpy.zeros(3)
    shifts = numpy.zeros(3)
    shifts[0] = alignmentList[3]
    shifts[1] = alignmentList[4]
    shifts[2] = 0
    angles[0] = alignmentList[0]
    angles[1] = alignmentList[1]
    angles[2] = alignmentList[2]

    matrix = matrixFromGeometry(shifts, angles, inverseTransform)
    alignment.setMatrix(matrix)

    return alignment


def iterParticlesByMic(partSet):
    """ Iterate the particles ordered by micrograph """
    for i, part in enumerate(partSet.iterItems(orderBy=['_micId', 'id'],
                                               direction='ASC')):
        yield i, part


def convertReferences(refSet, outputFn):
    """ Simplified version of writeSetOfParticles function.
    Writes out an hdf stack.
    """
    fileName = ""
    a = 0
    proc = Plugin.createEmanProcess(args='write')

    for part in refSet:
        objDict = part.getObjDict()
        objDict['hdfFn'] = outputFn
        objDict['_itemId'] = part.getObjId()

        # the index in EMAN begins with 0
        if fileName != objDict['_filename']:
            fileName = objDict['_filename']
            if objDict['_index'] == 0:
                a = 0
            else:
                a = 1
        objDict['_index'] = int(objDict['_index'] - a)

        # Write the e2converter.py process from where to read the image
        print(json.dumps(objDict), file=proc.stdin)
        proc.stdin.flush()
        proc.stdout.readline()
    proc.kill()


def calculatePhaseShift(ampcont):
    # calculate phase shift as in EMAN2 ctf.cpp
    if -100.0 < ampcont <= 100.0:
        PhaseShift = numpy.arcsin(ampcont / 100.0)
    elif ampcont > 100.0:
        PhaseShift = numpy.pi - numpy.arcsin(2.0 - ampcont / 100.0)
    else:
        PhaseShift = -numpy.pi - numpy.arcsin(-2.0 - ampcont / 100.0)
    ctfPhaseShift = numpy.rad2deg(PhaseShift)

    return ctfPhaseShift


def coordinates2json(pathInputCoor, inputCoor):
    coords = []
    for coor in inputCoor.iterCoordinates():
        coords.append([coor.getX(), coor.getY(), coor.getZ(), "manual", 0.0, 0])

    coordDict = {"boxes_3d": coords,
                 "class_list": {"0": {"boxsize": inputCoor.getBoxSize(), "name": "particles_00"}}
                 }

    writeJson(coordDict, pathInputCoor)


def getLastParticlesParams(directory):
    """
    Return a dictionary containing the params values of the last iteration.

    Key: Particle index (int)
    Value: Dict[{coverage: float, score: float, alignMatrix: list[float]}]
    """
    # JSON files with particles params: path/to/particle_parms_NN.json
    particleParamsPaths = glob.glob(os.path.join(directory, 'particle_parms_*.json'))
    if not particleParamsPaths:
        raise Exception("Particle params files not found")

    lastParticleParamsPath = sorted(particleParamsPaths)[-1]
    particlesParams = json.load(open(lastParticleParamsPath))
    output = {}

    for key, values in particlesParams.items():
        # key: '(path/to/particles/basename.hdf', nParticle)'
        # values: '{"coverage": 1.0, "score": 2.0, "xform.align3d": {"matrix": [...]}}'
        import re
        match = re.search(r'(\d+)\)$', key)
        if not match:
            continue
        particleIndex = int(match.group(1))
        coverage = values.get("coverage")
        score = values.get("score")
        alignMatrix = values.get("xform.align3d", {}).get("matrix")

        if coverage and score and alignMatrix:
            customParticleParams = dict(
                coverage=coverage,
                score=score,
                alignMatrix=alignMatrix
            )
            output[particleIndex] = customParticleParams

    return output


def updateSetOfSubTomograms(inputSetOfSubTomograms, outputSetOfSubTomograms, particlesParams):
    """Update a set of subtomograms from a template and copy attributes coverage/score/transform"""

    def updateSubTomogram(subTomogram, index):
        particleParams = particlesParams.get(index)
        if not particleParams:
            raise Exception("Could not get params for particle %d" % index)
        setattr(subTomogram, 'coverage', Float(particleParams["coverage"]))
        setattr(subTomogram, 'score', Float(particleParams["score"]))
        # Create 4x4 matrix from 4x3 e2spt_sgd align matrix and append row [0,0,0,1]
        am = particleParams["alignMatrix"]
        angles = numpy.matrix([am[0:3], am[4:7], am[8:11], [0, 0, 0]])
        samplingRate = outputSetOfSubTomograms.getSamplingRate()
        shift = numpy.matrix([am[3] * samplingRate, am[7] * samplingRate, am[11] * samplingRate, 1])
        matrix = numpy.concatenate((angles, shift.T), axis=1)
        subTomogram.setTransform(Transform(matrix))

    outputSetOfSubTomograms.copyItems(inputSetOfSubTomograms,
                                      updateItemCallback=updateSubTomogram,
                                      itemDataIterator=itertools.count(0))
