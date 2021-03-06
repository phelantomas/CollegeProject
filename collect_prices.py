'''
Author: Tomas Phelan
License Employed: GNU General Public License v3.0
Brief: Includes functions for retrieving and storing bitcoin prices
        This is intended to run every hour.
'''

import requests
import json

def get_price_info(type):
    try:
        url = 'https://api.cryptonator.com/api/ticker/{}'.format(type)
        response = requests.get(url)
        return response.text
    except:
        return None
    

def write_price_to_file(price, fname):
    if price:
        try:
            with open(fname, 'a') as f:
                f.write(str(price.text)+"\n")
            print("Successfully wrote price")
        except:
            print("Error writing price to '" + fname + "'")
    else:
        print("No tweet to write")
  
def collect_price():
    p = get_price_info()

if __name__ == "__main__":
    p = get_price_info()
    write_price_to_file(p, 'prices.txt')
