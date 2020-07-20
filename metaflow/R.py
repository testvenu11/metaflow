import os
import imp
from tempfile import NamedTemporaryFile

from .util import to_bytes

R_FUNCTIONS = {}
R_PACKAGE_PATHS = None
RDS_FILE_PATH = None
R_VERSION = None

def call_r(func_name, args):
    R_FUNCTIONS[func_name](*args)

def get_r_func(func_name):
    return R_FUNCTIONS[func_name]

def package_paths():
    if R_PACKAGE_PATHS is not None:
        root = R_PACKAGE_PATHS['package']
        prefixlen = len('%s/' % root.rstrip('/'))
        for path, dirs, files in os.walk(R_PACKAGE_PATHS['package']):
            if '/.' in path:
                continue
            for fname in files:
                if fname[0] == '.':
                    continue
                p = os.path.join(path, fname)
                yield p, os.path.join('metaflow-r', p[prefixlen:])
        flow = R_PACKAGE_PATHS['flow']
        yield flow, os.path.basename(flow)

def entrypoint():
    return 'PYTHONPATH=/root/metaflow R_LIBS_SITE=`Rscript -e \'cat(paste(.libPaths(), collapse=\\":\\"))\'`:metaflow/ Rscript metaflow-r/run_batch.R --flowRDS=%s' % RDS_FILE_PATH

def use_r():
    return R_PACKAGE_PATHS is not None

def container_image():
    rocker_ml_tags = ["3.5.2", "3.5.3", "3.6.0", "3.6.1", "4.0.0", "4.0.1", "4.0.2"]

    rocker_tag = R_VERSION
    if R_VERSION not in rocker_ml_tags:
        r_version= ".".join(R_VERSION.split(".")[0:2])
        if (r_version < "3.5"):
            rocker_tag = "3.5.2"
        elif (r_version == "3.5"):
            rocker_tag = "3.5.3"
        elif (r_version == "3.6"):
            rocker_tag = "3.6.1"
        else:
            rocker_tag = "4.0.2"

    return "rocker/ml:%s" % rocker_tag 

def working_dir():
    if use_r(): 
        return R_PACKAGE_PATHS['wd']
    return None

def run(flow_script, r_functions, rds_file, metaflow_args, full_cmdline, r_paths, r_version):
    global R_FUNCTIONS, R_PACKAGE_PATHS, RDS_FILE_PATH, R_VERSION

    R_FUNCTIONS = r_functions
    R_PACKAGE_PATHS = r_paths
    RDS_FILE_PATH = rds_file
    R_VERSION = r_version

    # there's some reticulate(?) sillyness which causes metaflow_args
    # not to be a list if it has only one item. Here's a workaround
    if not isinstance(metaflow_args, list):
        metaflow_args = [metaflow_args]
    # remove any reference to local path structure from R
    full_cmdline[0] = os.path.basename(full_cmdline[0])
    with NamedTemporaryFile(prefix="metaflowR.", delete=False) as tmp:
        tmp.write(to_bytes(flow_script))
    module = imp.load_source('metaflowR', tmp.name)
    flow = module.FLOW(use_cli=False)

    from . import exception 
    from . import cli 
    try:
        cli.main(flow,
                 args=metaflow_args,
                 handle_exceptions=False,
                 entrypoint=full_cmdline[:-len(metaflow_args)])
    except exception.MetaflowException as e:
        cli.print_metaflow_exception(e)
        os.remove(tmp.name)
        os._exit(1)
    except Exception as e:
        import sys
        print(e)
        sys.stdout.flush()
        os.remove(tmp.name)
        os._exit(1)
    finally:
        os.remove(tmp.name)
