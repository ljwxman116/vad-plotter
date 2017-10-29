from __future__ import print_function

from MesoPy import Meso #Get MesoPy here: https://github.com/mesowx/MesoPy
import MesoPy
from datetime import datetime as dt
from time import strftime,gmtime

import numpy as np

import sys

from vad_reader import download_vad, VADFile
from params import compute_parameters
from plot import plot_hodograph
from wsr88d import nwswfos

import re
import argparse
from datetime import timedelta
import json

def wind(id):
    m=Meso(token='YOUR TOKEN') #add your MesoWest API token here. For more info, go to the MesoPy repository: https://github.com/mesowx/MesoPy
    latest=m.latest(stid=id,within='30',units='ENGLISH')
    ob=latest['STATION'][0]
    try:
        wd=int(ob['OBSERVATIONS']['wind_direction_value_1']['value'])
        wdt=ob['OBSERVATIONS']['wind_direction_value_1']['date_time'] 
        wdtstrp=dt.strptime(wdt, '%Y-%m-%dT%H:%M:%SZ')
        wdtz=dt.strftime(wdtstrp,'%m-%d-%Y %H:%Mz')
    except KeyError:
	    wd=None
    try:
        ws=int(ob['OBSERVATIONS']['wind_speed_value_1']['value'])
        wst=ob['OBSERVATIONS']['wind_speed_value_1']['date_time'] 
        wststrp=dt.strptime(wst, '%Y-%m-%dT%H:%M:%SZ')
        wstz=dt.strftime(wststrp,'%m-%d-%Y %H:%Mz')
    except KeyError:
	     ws=None
    if wd is None or ws is None:
        sfcw=None
        sfcwt=None
    else:
        sfcw='%s/%s'%(wd,ws)
        if wdtz==wstz:
            sfcwt=wdtz
        else:
            sfcwt='wd @ %s & ws @ %s'%(wdtz,wstz)
    return sfcw,sfcwt

"""
vad.py
Author:     Tim Supinie (tsupinie@ou.edu)
Completed:  May 2012
Modified:   26 April 2015
                Fixed SRH calculations.
            28 December 2015
                Migrated to its own package, ravamped plot, fixed SRH calculations for real this time.
            30 March 2016
                Fixed RMS error circle size, and added Bunkers motion vector calculations.
"""

def is_vector(vec_str):
    return bool(re.match(r"[\d]{3}/[\d]{2}", vec_str))


def parse_vector(vec_str):
    return tuple(int(v) for v in vec_str.strip().split("/"))


def parse_time(time_str):
    no_my = False
    now = dt.utcnow()
    if '-' not in time_str:
        no_my = True

        year = now.year
        month = now.month
        time_str = "%d-%d-%s" % (year, month, time_str)

    plot_time = dt.strptime(time_str, '%Y-%m-%d/%H%M')

    if plot_time > now:
        if no_my:
            if month == 1:
                month = 12
                year -= 1
            else:
                month -= 1
            time_str = "%d-%d-%s" % (year, month, time_str)
            plot_time = dt.strptime(time_str, '%Y-%m-%d/%H%M')
        else:
            raise ValueError("Time '%s' is in the future." % time_str)

    return plot_time

def vad_plotter(radar_id, storm_motion='right-mover', sfc_wind=None, time=None, fname=None, local_path=None, web=False, fixed=False):
    plot_time = None
    if time:
        plot_time = parse_time(time)
    elif local_path is not None:
        raise ValueError("'-t' ('--time') argument is required when loading from the local disk.")

    if not web:
        print("Plotting VAD for %s ..." % radar_id)

    if local_path is None:
        vad = download_vad(radar_id, time=plot_time)
    else:
        iname = "%s/%s%s_SDUS34_NVW%s_%s" % (local_path, radar_id[0], nwswfos[radar_id], radar_id[1:], plot_time.strftime("%Y%m%d%H%M"))
        vad = VADFile(open(iname, 'rb'))

    vad.rid = radar_id

    if not web:
        print("Valid time:", vad['time'].strftime("%d %B %Y %H%M UTC"))

    if sfc_wind:
        sfc_wind = parse_vector(sfc_wind)
        vad.add_surface_wind(sfc_wind)

    params = compute_parameters(vad, storm_motion)
    plot_hodograph(vad, params, fname=fname, web=web, fixed=fixed, archive=(local_path is not None))


def main():
    tt=strftime('%m-%d-%Y %H:%Mz',gmtime())
    print('Current Time: %s'%tt)
	
    ap = argparse.ArgumentParser()
    ap.add_argument('radar_id', help="The 4-character identifier for the radar (e.g. KTLX, KFWS, etc.)")
    ap.add_argument('-m', '--storm-motion', dest='storm_motion', help="Storm motion vector. It takes one of two forms. The first is either 'BRM' for the Bunkers right mover vector, or 'BLM' for the Bunkers left mover vector. The second is the form DDD/SS, where DDD is the direction the storm is coming from, and SS is the speed in knots (e.g. 240/25).", default='right-mover')
    ap.add_argument('-id','--sfc-id',dest='sfc_id',help='Station ID to get surface wind direction and wind speed from. Ex: krfd or KRFD')
    ap.add_argument('-s', '--sfc-wind', dest='sfc_wind', help="Surface wind vector. It takes the form DDD/SS, where DDD is the direction the wind is coming from, and SS is the speed in knots (e.g. 240/25).")
    ap.add_argument('-t', '--time', dest='time', help="Time to plot. Takes the form DD/HHMM, where DD is the day, HH is the hour, and MM is the minute.")
    ap.add_argument('-f', '--img-name', dest='img_name', help="Name of the file produced.")
    ap.add_argument('-p', '--local-path', dest='local_path', help="Path to local data. If not given, download from the Internet.")
    ap.add_argument('-w', '--web-mode', dest='web', action='store_true')
    ap.add_argument('-x', '--fixed-frame', dest='fixed', action='store_true')
    args = ap.parse_args()

    np.seterr(all='ignore')

    id=args.sfc_id
    if id is None:
        sfcw=args.sfc_wind
        if sfcw is None:
            pass
        else:
            print('Sfc wind being used: %s'%sfcw)
    else:
        try:
            sfcw,sfcwt=wind(id) #should check if wind data is old. 
            print('Surface wind from %s being used: %s @ %s'%(id.upper(),sfcw,sfcwt))
        except MesoPy.MesoPyError:
            print('*MesoPy Error* Not using sfc wind data. Did you enter the correct station ID? ')
            sfcw=None

    try:
        vad_plotter(args.radar_id.upper(),
            storm_motion=args.storm_motion,
            sfc_wind=sfcw,
            time=args.time,
            fname=args.img_name,
            local_path=args.local_path,
            web=args.web,
            fixed=args.fixed
        )
    except:
        if args.web:
            print(json.dumps({'error':'error'}))
        else:
            raise

if __name__ == "__main__":
    main()