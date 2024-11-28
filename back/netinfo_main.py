import   paramiko
import   re
import   asyncio
import   sys
import   pandas as pd
import   argparse
import   time
import   logging
import   collections 
import   inspect

import   netinfo_util as util
import   netinfo_db as db

import   settings

username = "jtx.switchbackup"
password = "1W4cR2zaVeva3YSHzTcz"

# lab option for user
username = "cisco"
password = "cisco"

## Devices list: ALL devices list have the same structure:
## device = {'name' : id,'ip': ip}
#_visitedDevices = []

_dbHandler = None



## ------------------------------------------------------------------
## ------------------------------------------------------------------

async def getNodeInfo (_dbHandler, ip, getInfo):

  deviceID = None
  adminIP = None
  serialNum = None
  hostname = None
  uptime = None
  platform = None
  neighborsList = []  # list of devices discovered via CDP and / or LLDP
  accessOK = False

  try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password, port=22, timeout=10)    
    commandsShell = ssh.invoke_shell()
    
    logging.info( "Connecting to: %s" % ip )

    #print("Connected to %s" % ip)
  except paramiko.AuthenticationException:
    print("Failed to connect to %s due to wrong username/password" %ip)
    await db.dbUpdateUnaccesibleDevices(_dbHandler, ip)
    return ( (accessOK, hostname, ip, neighborsList) )
  except Exception as e:
    print(e)    
    await db.dbUpdateUnaccesibleDevices(_dbHandler, ip)
    return ( (accessOK, hostname, ip, neighborsList) )

  accessOK = True
    
  # avoid pages scroll control (cisco term len 0) 
  await(util.execCommand(commandsShell, 'term len 0', ip))

  # get device ID from 'show version'
  print("getting serial, uptime, hostname...")
  data = await(util.execCommand(commandsShell, 'show ver', ip ))
  (serialNum, hostname, uptime, platform) = await(util.processShowVer(data))
  print( "THIS DEVICE: Serial: {} Hostname: {}  Uptime: {}".format(serialNum, hostname, uptime) ) 
 
  # insert / update into Database
  if (serialNum is not None and hostname is not None):
    thisDevice = {'name' : hostname,'ip': ip}
    myDeviceData = {'hostname' : hostname, 'ip': ip, 'serialNum': serialNum, 'uptime': uptime, 'platform': platform }
    await db.dbUpdateDevices(_dbHandler, [myDeviceData])          # update Devices info into DB
    (deviceID, adminIP) = await db.dbGetDeviceID(_dbHandler, hostname)  ## get from DB, reuired for subsequent updates / inserts as primary key

  # get list of CDP neighbors. 
  print(f"getting CDP Info from IP {ip}...")
  devicesCDPData = await(util.execCommand(commandsShell, 'show cdp nei deta', ip))
  devicesCDP = await util.parseCDP(devicesCDPData)     # parse CDP info

  # get list of LLDP neighbors. 
  print("getting LLDP Info...")
  devicesLLDPData = await(util.execCommand(commandsShell, 'show lldp nei deta', ip))
  devicesLLDP = await util.parseLLDP(devicesLLDPData)     # parse LLDP info

  print("CDP List:", devicesCDP)
  print("LLDP List: ",  devicesLLDP)

  ## build one unique list of devices
  ## ALL devices list have the same structure:
  ## device = {'name' : id,'ip': ip}
  for d in devicesCDP:
    if d not in neighborsList:
      neighborsList.append(d)
  for d in devicesLLDP:
    if d not in neighborsList:
      neighborsList.append(d)

  
  print(f"deviceID: {deviceID}")
  if ( deviceID is None ):
    logging.info( "No device ID to update ARP / MAC Info (IP: {} name: {}) ".format(ip, hostname))
  else: 
    if ( getInfo == True):
      """
      # get interfaces list
      print("getting interfaces...")
      data = await(util.execCommand(commandsShell, 'show interface status', ip))
      if (data is not None):
        iFaceList = await(util.processIFACE(data, deviceID, hostname, ip, serialNum ))
        if (iFaceList is not None):
          print(iFaceList)  
          await db.dbUpdateiFaceList(_dbHandler, iFaceList, hostname)          # update ARP info info into DB
     
      # get MAC Address list
      print("getting MAC Addresses...")
      data = await(util.execCommand(commandsShell, 'show mac address', ip))
      if (data is not None):
        macList = await(util.processMAC(data, deviceID, hostname, ip, serialNum ))
        if (macList is not None):
          print(macList)  
          await db.dbUpdateMACList(_dbHandler, macList, hostname)          # update MAC info info into DB

      # get ARP list
      print("getting ARP...")
      data = await(util.execCommand(commandsShell, 'show arp', ip))
      if (data is not None):
        arpList = await(util.processARP(data, deviceID, hostname, ip, serialNum ))
        if (arpList is not None):
          print(arpList)  
          await db.dbUpdateARPList(_dbHandler, arpList, hostname)          # update ARP info info into DB  """
      # get 'show int | i (protoc|error|ut rate)'  (errors, interface, traffic)
      data = await(util.execCommand(commandsShell, 'show int | i (protoc|error|ut rate)', ip))
      if (data is not None):
        interfaceErrorsList = await(util.processIntErrors(data, deviceID, hostname, ip, serialNum ))
        if (interfaceErrorsList is not None):
          await db.dbUpdateiFaceErrorList(_dbHandler, interfaceErrorsList, hostname)

          print(interfaceErrorsList)  
          print(len(interfaceErrorsList))  

  ## close comms. as the rest is just parsing
  commandsShell.close()
  ssh.close()
 
  print("=============================================================================================")
  sys.stdout.flush()
  return ( (accessOK, hostname, ip, neighborsList) )

  
## ------------------------------------------------------------------
## ------------------------------------------------------------------

async def traverseNetNonrecursive(_dbHandler, ip, depth, getInfo):

  deviceID = None
  adminIP = None
  serialNum = None
  hostname = None
  uptime = None
  DevAccessOK =  False
  devHostname = None 
  devIP = None
  
  neighborsList = []  # list of devices discovered via CDP and / or LLDP
  nodeList = []
  hostnamesVisited = []

  thisDevice = {'name' : '---', 'ip': ip}
  nodeList.append(thisDevice)
  
  i = 0  
  while i < len(nodeList):  
    nodeToVisit = nodeList[i]
    #print(i, ' - ', len(nodeList), ' - ', nodeToVisit)

    print('*********************************************')
    print("Node list length: {}  visited nodes OK: {}".format(len(nodeList), len(hostnamesVisited)))
    print('*********************************************')
    
    print(" +++ getting into device name: {}  IP: {}".format(nodeToVisit['name'],nodeToVisit['ip']))
    (DevAccessOK, devHostname, devIP, neighborsList) = await (getNodeInfo (_dbHandler, nodeToVisit['ip'], getInfo))

    if ( not DevAccessOK ):    ## error in access to device,  try again with Admin IP from database... (in some cases LLDP / CDP get secondary IPs)
      if (nodeToVisit is not None and len(nodeToVisit['name'].strip()) > 5):
        (deviceID, adminIP) = await db.dbGetDeviceID(_dbHandler, nodeToVisit['name'].strip())  ## get Admin IP from DB
        if ( adminIP is not None and ip.strip() != adminIP.strip()):
          print(" +++ getting into device name: {}  IP: {}".format(nodeToVisit['name'], adminIP.strip()))
          (DevAccessOK, devHostname, devIP, neighborsList) = await (getNodeInfo (_dbHandler, adminIP.strip(), getInfo))


    if ( DevAccessOK ):    # if node / switch data retrieval was succesful, add to the list of 
                           # already visited nodes (by hostname, as a hostname should be uniqe and mey have many IPs)
    
      if(i == 0):  # first visitede device / switch doesn't have a name, so update it!
        nodeList[0]['name'] = devHostname
    
      if devHostname not in hostnamesVisited:
        hostnamesVisited.append(devHostname)

      ## update neighbors into DB, for future reference
      await db.updateNeighbors(_dbHandler, ip,  devHostname, neighborsList)
      

      ## we check CDP / LLDP list and add to the TODO list 
      ## only if the hostname is not already there (already visited, 
      ## this also avoid duplicates as any hostname migth be preent with 
      ## different IPs)
      for node in neighborsList:
        if node['name'] not in hostnamesVisited:     # not visiteed before
          hostsList = [d['name'] for d in nodeList]  
          if node['name'] not in hostsList:          # not already inserted  
            nodeList.append(node)

    if (depth == 0):  ## for one shot!
      print ("-------------------------------------------")
      print ("neighborsList: ")
      for n in  neighborsList:
        print ( "name: %40s IP: %s" % (n['name'], n['ip'])) 
      print ("-------------------------------------------")
      print ("nodeList: ")
      for n in  nodeList:
        print ( "name: %40s IP: %s" % (n['name'], n['ip'])) 
      print ("-------------------------------------------")

      break;   

    
          
    i += 1  

  print("=============================================================================================")
  sys.stdout.flush()
  return (True)

  
## ------------------------------------------------------------------
## ------------------------------------------------------------------

async def main():

  ip = ''
  depth = 200
  getInfo = False
  sendToDb = True
  print("Start...")
  visitedDevices = []

  parser = argparse.ArgumentParser(description='Traffic totalization.')
  parser.add_argument('-i', '--ip', help='IP address of switch to interrogate', required=True)
  parser.add_argument('-g', '--getInfo', nargs='?', help='Get MAC / ARp / INTERFACE Info from switch', default=False)
  parser.add_argument('-d', '--depth', help='Depth to go 0: this device only (how many levels or jumps through switches...[200]', required=False)
  parser.add_argument('-n', '--noDB', nargs='?', default=False, help='NO DB connection, for debugging only', required=False)
  parser.add_argument('-v', '--verbose', action='count', default=0, help='Enables a verbose mode [-v, -vv, -vvv]')
  parser.add_argument('-D', '--debug', action='count', default=0, help='Debug level [-D, -DD, -DDD]')

  try:
    args = vars(parser.parse_args())
  except:
    parser.print_help()
    sys.exit(0)

  if args['ip']:
    ip = args['ip']  
  if args['depth']:
    depth = int(args['depth'])

  if args['verbose'] != None:
    settings.verbose = int(args['verbose'])

  if args['debug'] != None:
    settings.debug = int(args['debug'])

  if args['getInfo'] != False:
    getInfo = True

  if args['noDB'] != False:
    sendToDb = False

  FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
  logging.basicConfig(filename= sys.argv[0] + ".log", level=logging.INFO, format=FORMAT)
  logging.info( sys.argv[0] + ' Started !!!')

  if sendToDb:
    _dbHandler = await db.dbConnect()
    if (_dbHandler is None):
      logging.info( sys.argv[0] + ' DB init error. Exiting....')
      exit(1)
    else:
      logging.info( sys.argv[0] + ' DB init OK! ')
  else:
    _dbHandler = None
   
  # remember to import 'inspect' 
  print( ' ---- line', inspect.getframeinfo(inspect.currentframe()).lineno, 'of file', inspect.getframeinfo(inspect.currentframe()).filename )
   
  # run command over first switch
  visitedDevices = await (traverseNetNonrecursive(_dbHandler, ip, depth, getInfo))
  print(visitedDevices) 

  if (depth == 0):  ## for one shot!
    return()

  # check if we have devices not detected / visited in DB
  # some switches are not discovered by LLDP or CDp so we will 
  # always use DB as last resource to ensure every device gets updated

  notDiscoveredDevices = await db.dbGetDeviceNotUpdated(_dbHandler, 50)
  if  notDiscoveredDevices is not None and len(notDiscoveredDevices) > 0:
    print(notDiscoveredDevices)
    for n in notDiscoveredDevices:
      visitedDevices = await (traverseNetNonrecursive(_dbHandler, n, 0, True))
      print(visitedDevices) 
      
  if sendToDb:
    await db.dbClose(_dbHandler)
  
  logging.info( sys.argv[0] + ' ends OK !')
  return() 

## ------------------------------------------------------------------

if __name__ == "__main__":
    import time
    s = time.perf_counter()
    asyncio.run(main())
    elapsed = time.perf_counter() - s
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")

## ------------------------------------------------------------------
## ------------------------------------------------------------------

