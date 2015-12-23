#! /usr/bin/env python
__author__ = 'cbn'

from collections import namedtuple
import cStringIO
import json
import urllib
from PIL import Image
from redis import StrictRedis
from sys import argv
from os.path import abspath
from multiprocessing import Pool
import logging
import cooperhewitt.swatchbook as sb
import itertools

logging.basicConfig(filename='logs/deets.log',level=logging.DEBUG)

def get_item_details(filename):
    filepath = abspath(filename)
    r = StrictRedis()
    essentials = []
    for line in open(filepath):
        if line.startswith("[") or line.startswith("]"):
            continue
        line = line.lstrip(",")
        x = json.loads(line)["_source"]
        if x.get('object',None) and not r.exists("done:" + x["@id"]):
            record = {
                "id"    : x['@id'],
                "thumb" : x['object'],
                "url"   : x['isShownAt'],
                }
            if x['sourceResource'].get("title", None):
                if isinstance(x['sourceResource']['title'], basestring):
                    record["title"] = x['sourceResource']['title']
                else:
                    record["title"] = x['sourceResource']['title'][0]
            else:
                record["title"] = "Untitled"
            yield record
        else:
            print "boo"

def load_remote_image(url):
    try:
        file = cStringIO.StringIO(urllib.urlopen(url).read())
        return Image.open(file)
    except Exception as e:
        logging.debug("Error while trying to get thumbnail at %s" % (url) )
        logging.debug(e)
        return False


def get_image_colors(image):
    css3_colors={}
    if image.mode != "RGB":
        image = image.convert("RGB")

    size = image.size[0] * image.size[1]
    colors = image.getcolors(size)
    # calculate what percentage the color is of total image
    # and transform RGB value to hex.
    for pixel_count,color in colors:
        actual_hex = "#%02x%02x%02x" % color
        css3_hex   = sb.closest('css3', actual_hex)[0]
        if css3_colors.get(css3_hex, None):
            css3_colors[css3_hex] += pixel_count
        else:
            css3_colors[css3_hex] =  pixel_count

    # find the top 5 percentages
    if len(css3_colors) >= 5:
        lowest_pixel_value = sorted(css3_colors.values())[-5]
    else:
        lowest_pixel_value = sorted(css3_colors.values())[-len(css3_colors)]

    topFive =  [(round(pixels * 1.0 / size, 2), color ) for color, pixels in css3_colors.iteritems() if pixels >= lowest_pixel_value]
    return topFive

def add_to_redis(record, colors):
    r = StrictRedis()
    value = json.dumps(record)
    for score, color in colors:
        r.zadd(color, score, value)
    r.sadd("done:" + record['id'],"True" )

def run(deet):
    logging.debug("Working on " + deet["id"])
    image = load_remote_image(deet['thumb'])
    if image:
        colors = get_image_colors(image)
        add_to_redis(deet, colors)

if __name__ == "__main__":
    p = Pool(4)
    deets = get_item_details(argv[1])
    p.map(run, itertools.islice(deets, 0, None))
    p.close()
    p.join()
