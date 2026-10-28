"""Train the yield model.  python train.py [--csv your_data.csv]"""
import argparse
import json

from agri.model import train

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="optional real dataset (see agri/model.py docstring)")
    args = ap.parse_args()
    print(json.dumps(train(args.csv), indent=2))
