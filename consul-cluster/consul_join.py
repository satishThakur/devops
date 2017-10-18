import consul
import time
import logging
from functools import wraps
from subprocess import call

def retry(ExceptionToCheck, tries=4, delay=15, backoff=2, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """
    def deco_retry(f):

        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck, e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print msg
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry

@retry(Exception)	
def get_cluster_ips(asg_name,def_ips,logger):		
	return def_ips
 

def getlogger():
	logger = logging.getLogger(__name__)
	logger.setLevel(logging.INFO)
    
    # create a file handler
	handler = logging.FileHandler('/data/consul/logs/consul_join.log')
	handler.setLevel(logging.INFO)

	# create a logging format
	formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	handler.setFormatter(formatter)

	# add the handlers to the logger
	logger.addHandler(handler)
	logger.addHandler(logging.StreamHandler())
	return logger


@retry(Exception, tries=30, delay=30, backoff=1)
def join_cluster(ips,clustersize,logger):
	logger.info("Trying to join cluster...")
	c = consul.Consul()
	for ip in ips:
		try:
			call(["consul", "join", ip])
			result = c.agent.join(ip)
			logger.info("Joining %s %s", ip,(" success" if result else " failed"))
		except Exception, e:
			#logger.info("Joining %s Failed", ip)
			logger.exception("Join Failed")	
	members = len(c.agent.members())
	logger.info("expected members %d actual %d", clustersize, members)
	if members < clustersize:
		raise Exception('Not enough members')
	else:
		logger.info("All members")
		for member in c.agent.members():
			logger.info("%s      %s",member["Name"],member["Addr"])


def loadproperties(filepath):
	separator = ":"
	keys = {}
	with open(filepath) as f:
		for line in f:
			if separator in line:
				# Find the name and value by splitting the string
				name, value = line.split(separator, 1)
				# Assign key value pair to dict
				# strip() removes white space from the ends of strings
				keys[name.strip()] = value.strip()
	return keys
	

if __name__ == "__main__":
	props = loadproperties("/vagrant/consul.properties")
	logger = getlogger()
	logger.info("Consul properties: %s", props)
	try:
		clustersize = props["clustersize"]
		asgname = props["asgname"]
		def_ips = []
		for ip in props["defaultips"].split(","):
			def_ips.append(ip.strip())
		
		logger.info("Default ips are: %s", def_ips)
		ips = get_cluster_ips("",def_ips,logger)
		join_cluster(ips,int(clustersize),logger)
	except Exception,e:
		logger.info(e)
