import os, sys, json, base64, time, datetime, shutil
from collections import OrderedDict
sys.dont_write_bytecode=True
from minio import Minio
from minio.error import ResponseError
import docker, requests
import boto3
import yaml


def package_name():
    with open('universe/package.json', 'r') as f:
         package = json.load(f)
    return package['name']


def package_version():
    with open('universe/package.json', 'r') as f:
         package = json.load(f)
    return package['version']


def sdk_version():
    with open('universe/package.json', 'r') as f:
         package = json.load(f)
    return package['tags'][0]


def sha_values():
    r = requests.get('https://downloads.mesosphere.com/dcos-commons/artifacts/'+sdk_version()+'/SHA256SUMS')
    return {e[1]:e[0] for e in map(lambda e: e.split('  '), str(r.text).split('\n')[:-1])}


def _read_config_values(artifacts_url):
    global_values = {
        'time_epoch_ms': str(int(time.time()*1000)), 
        'time_str': datetime.datetime.utcnow().isoformat(),
        'package-version': package_version(),
        "artifacts_url": artifacts_url,
    }
    config_values = dict()
    if os.path.exists("config.yml"):
        with open("config.yml") as f:
            config_values = yaml.safe_load(f.read()).get("values", dict())
    return {**config_values, **global_values}

def _prerender_file(config_values, filename):
    with open(filename) as f:
        data = f.read()
    return data % config_values


def _read_file(filename):
    with open(filename) as f:
        return f.read()


def build_repo(version='snapshot', releaseVersion=0, artifacts_url=""):
    if not artifacts_url:
        artifacts_url = 'http://minio.marathon.l4lb.thisdcos.directory:9000/artifacts/'+package_name()
    config_values = _read_config_values(artifacts_url)
    repository = {'packages': [] }
    packages = repository['packages']

    package = json.loads(_prerender_file(config_values, 'universe/package.json'), object_pairs_hook=OrderedDict)
    config = json.loads(_read_file('universe/config.json'), object_pairs_hook=OrderedDict)
    resource = json.loads(_prerender_file(config_values, 'universe/resource.json'), object_pairs_hook=OrderedDict)
    marathon = base64.b64encode(_prerender_file(config_values, 'universe/marathon.json.mustache').encode("utf-8")).decode("utf-8")

    if os.path.exists('java/scheduler/build/distributions/operator-scheduler.zip'):
         resource['assets']['uris']['scheduler-zip'] = artifacts_url+'/operator-scheduler.zip'

    package['version'] = version
    package['releaseVersion'] = releaseVersion
    package['config'] = config
    package['resource'] = resource
    package['marathon'] = {"v2AppMustacheTemplate": marathon}

    packages.append(package)
    os.makedirs("dist", exist_ok=True)
    with open('dist/'+package_name()+'-repo.json', 'w') as file:
         file.write(json.dumps(repository, indent=4))


def collect_artifacts():
    artifacts = [str('dist/'+package_name()+'-repo.json')]
    if os.path.exists("files"):
        artifacts.extend([os.path.join("files", f) for f in os.listdir('files')])
    if os.path.exists("svc.yml"):
        artifacts.append("svc.yml")
    if os.path.exists('java'):
       java_projects = ['java/'+f for f in os.listdir('java') if os.path.isdir('java/'+f)]
       dists = {jp+'/build/distributions':os.listdir(jp+'/build/distributions') for jp in java_projects}
       artifacts.extend([d+'/'+f for d in dists for f in dists[d]])
    return artifacts


def copy_artifacts(artifacts, target_dir):
    for a in artifacts:
        dest = a.split(os.path.sep)[-1]
        shutil.copyfile(a, os.path.join(target_dir, dest))


def upload_minio(artifacts):
    minio_host = os.environ['MINIO_HOST']
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minio")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minio123")
    minioClient = Minio(minio_host, access_key=access_key, secret_key=secret_key, secure=False)

    for a in artifacts:
        try:
           file_stat = os.stat(a)
           file_data = open(a, 'rb')
           minioClient.put_object('artifacts', package_name()+'/'+os.path.basename(a), file_data, file_stat.st_size, content_type='application/vnd.dcos.universe.repo+json;charset=utf-8;version=v4')
        except ResponseError as err:
           print(err)

def upload_aws(artifacts, bucket, package_version):
    s3 = boto3.client('s3')

    for a in artifacts:
        with open(a, "rb") as f:
             s3.upload_fileobj(f, bucket, 'packages/'+package_name()+'/'+package_version+'/'+os.path.basename(a), ExtraArgs={'ACL': 'public-read', 'ContentType': 'application/vnd.dcos.universe.repo+json;charset=utf-8;version=v4'})


def write_universe_files(release_version, artifacts_url, universe_path, force, is_complete_path=False):
    config_values = _read_config_values(artifacts_url)
    
    if is_complete_path:
        path = universe_path
    else:
        path = universe_path+'/packages/'+package_name()[0].upper()+'/'+package_name()
        if not os.path.exists(path):
            print('>>> ERROR: package folder %s does not exist' % path)
            return
        path = path+'/'+str(release_version)
    if not force and not is_complete_path and os.path.exists(path):
        print('>>> ERROR: release version foler \''+release_version+'\' exists already !')
        return
    
    os.makedirs(path, exist_ok=True)
    package = _prerender_file(config_values, 'universe/package.json')
    config = _read_file('universe/config.json')
    resource = _prerender_file(config_values, 'universe/resource.json')
    marathon = _prerender_file(config_values, 'universe/marathon.json.mustache')

    with open(path+'/config.json', 'w') as f:
        f.write(config)
    with open(path+'/resource.json', 'w') as f:
        f.write(resource)
    with open(path+'/marathon.json.mustache', 'w') as f:
        f.write(marathon)
    with open(path+'/package.json', 'w') as f:
        f.write(package)
        
