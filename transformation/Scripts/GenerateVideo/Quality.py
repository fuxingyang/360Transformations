import subprocess as sub
import shutil
import os
import sys
import pickle

import LayoutGenerators

def FlatFixedResolutionToBitrate(ffLayout):
    height = ffLayout.height
    resToBitrate = {360:1000, 480: 2500, 720:5000, 1080:8000, 1440: 16000, 2160: 4000} #youtube recommandation
    closestRes = 360
    for res in resToBitrate:
        if abs(res-height) < abs(closestRes - height):
            closestRes = res
    return resToBitrate[closestRes]

def GenerateConf(ls, inputVideos, outputVideo, outputQuality, nbFrames, fps, bitrate):
    c = '[Global]\n'
    c += 'fps= {}\n'.format(fps)
    c += 'layoutFlow= ['
    first = True
    counter = 0
    for layouts_a in ls:
        if not first:
            c += ','
        else:
            first = False
        c += '["{}"'.format(inputVideos[counter])
        counter += 1
        for (l,a) in layouts_a:
            c += ', "{}"'.format( l.GetName() )
        c += ']'
    c += ']\n'
    c += 'displayFinalPict=false\n'
    c += 'videoOutputName= {}\n'.format(outputVideo)
    c += 'videoOutputBitRate={}\n'.format(bitrate)
    c += 'qualityOutputName= {}\n'.format(outputQuality)
    c += 'nbFrames={}\n'.format(nbFrames)

    layoutNames = []
    for layouts_a in ls:
        for (l,a) in layouts_a:
            if l.GetName() not in layoutNames:
                layoutNames.append(l.GetName())
                c+= l.GenerateLayout(a)
    return c


class QualityStorage:
    def __init__(self):
        self.goodQuality = {}
        self.badQuality = {}
        self.names = []

    def AddGood(self, name, LayoutId_quality, qec, centerRot):
        if name not in self.names:
            self.names.append(name)
            for (lId,q) in LayoutId_quality:
                if lId in self.goodQuality:
                    self.goodQuality[lId].append((q,qec,centerRot))
                else:
                    self.goodQuality[lId] = [(q,qec,centerRot)]

    def AddBad(self, name, LayoutId_quality, qec, centerRot):
        if name not in self.names:
            self.names.append(name)
            for (lId,q) in LayoutId_quality:
                if lId in self.badQuality:
                    self.badQuality[lId].append((q,qec,centerRot))
                else:
                    self.badQuality[lId] = [(q,qec,centerRot)]

    def IsNameInside(self, name):
        return name in self.names

    def Dump(self, fileName):
        with open(fileName, 'wb') as o:
            pickle.dump(self,o)

    @staticmethod
    def Load(fileName):
        with open(fileName, 'rb') as i:
            return pickle.load(i)

def GetAverageQuality(fileName):
    q = 0
    p = 0
    n = 0
    with open(fileName, 'r') as i:
        for line in i:
            (msssin, psnr) = line.split(' ')
            q += float(msssin)
            p += float(psnr)
            n += 1
    return (q/n, p/n) if n != 0 else 0

def ComputeFlatFixedQoE(config, trans, layoutsToTest, flatFixedLayout, fps, n, inputVideos, outputDirQEC, qec, flatFixedCenterRot, isGood):
    noOutputVideo = True
    if len(layoutsToTest) != len(inputVideos):
        raise ValueError("layoutsToTest and inputVideos should have the same lenth")
    layouts = []
    for ls in layoutsToTest:
        newLs = list(ls)
        newLs.append((flatFixedLayout, None))
        layouts.append(newLs)

    outputQualityStorageName = '{}/quality_storage.dat'.format(outputDirQEC)
    if os.path.isfile(outputQualityStorageName):
        qs = QualityStorage.Load(outputQualityStorageName)
    else:
        qs = QualityStorage()

    name = layouts[-1][-2][0].GetName() + flatFixedLayout.GetName()
    #name = flatFixedLayout.GetName()
    print ('TEST name = ', name)
    if not qs.IsNameInside(name):
        print ('TEST name = ', name, ' start computation')

        newIv = []
        try:
            counter = 1
            for iv in inputVideos:
                nivp = '/tmp/inputVideo{}_{}.mkv'.format(counter, os.path.splitext(os.path.basename(iv))[0])
                counter += 1
                shutil.copy(iv, nivp)
                newIv.append(nivp)
            with open(config, 'w') as cf:
                cf.write(GenerateConf(layouts, newIv, '' if noOutputVideo else '/tmp/test.mkv', '/tmp/test.txt', n, fps, FlatFixedResolutionToBitrate(flatFixedLayout)))

            sub.check_call([trans, '-c', config])

            i = 1
            for ls in layouts:
                (l,a) = ls[-2]
                name1 = l.GetName()
                (l,a) = ls[-1]
                name2 = l.GetName()
                outputVideoName = '/tmp/test{}{}.mkv'.format(i,name2)
                outputQualityName = '/tmp/test{}{}.txt'.format(i,name2)
                resultVideoName = '{}/{}_{}.mkv'.format(outputDirQEC, name1, name2)
                resultQualityName = '{}/{}_{}.txt'.format(outputDirQEC, name1, name2)
                resultLogName = '{}/{}_{}_log.txt'.format(outputDirQEC, name1, name2)
                if not noOutputVideo:
                    shutil.move(outputVideoName, resultVideoName)
                shutil.copy(config, resultLogName)
                if i != 1:
                    shutil.move(outputQualityName, resultQualityName)
                i += 1
        except:
            raise
        finally:
            for iv in newIv:
                if os.path.isfile(iv):
                    os.remove(iv)
            i = 1
            for ls in layouts:
                (l,a) = ls[-2]
                name1 = l.GetName()
                (l,a) = ls[-1]
                name2 = l.GetName()
                outputVideoName = '/tmp/test{}{}.mkv'.format(i,name2)
                outputQualityName = '/tmp/test{}{}.txt'.format(i,name2)
                if os.path.isfile(outputVideoName):
                    os.remove(outputVideoName)
                if os.path.isfile(outputQualityName):
                    os.remove(outputQualityName)
                i += 1

        lName_quality = []
        i = 1
        for ls in layouts:
            (l,a) = ls[-2]
            name1 = l.GetName()
            (l,a) = ls[-1]
            name2 = l.GetName()
            resultQualityName = '{}/{}_{}.txt'.format(outputDirQEC, name1, name2)
            if i != 1:
                lName_quality.append((name1, GetAverageQuality(resultQualityName)))
            i += 1

        print ("Add quality: ", lName_quality)

        if isGood:
            qs.AddGood(name, lName_quality, qec, flatFixedCenterRot)
        else:
            qs.AddBad(name, lName_quality, qec, flatFixedCenterRot)

        qs.Dump(outputQualityStorageName)
