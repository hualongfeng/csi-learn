import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='CSI Plugin')
    parser.add_argument('--drivername', type=str, required=True, help='Name of the CSI driver')
    parser.add_argument('--v', type=int, default=0, help='Log level verbosity')
    parser.add_argument('--endpoint', type=str, required=True, help='CSI endpoint')
    parser.add_argument('--nodeid', type=str, required=True, help='Node ID')
    parser.add_argument('--volume-root', type=str, default='/mnt/hostpath', help='Root directory for volumes')
    return parser.parse_args()