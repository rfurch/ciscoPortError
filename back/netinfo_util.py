
import   time
import   re
import   logging

import   settings

## ------------------------------------------------------------------
## ------------------------------------------------------------------
## ------------------------------------------------------------------
## ------------------------------------------------------------------
## ------------------------------------------------------------------
## ------------------------------------------------------------------

# handles command execution on an already open console / channel (paramiko)

async def execCommand(commandsShell, command, ip):

  try:
    if settings.verbose > 1:
      print(f"+++++ execCommand: {command}")
    commandsShell.send(command + '\n')
  except Exception as e:
    print(f"execCommand exeption: {e}")
    print (f"execCommand: Exception found on host:  %s " % (ip))

  alldata=''
  time.sleep(1)   
  if commandsShell is not None and commandsShell.recv_ready():
    alldata = commandsShell.recv(60000)
  while commandsShell.recv_ready():
    time.sleep(1)   
    alldata += commandsShell.recv(60000)
    time.sleep(1) 
    if settings.verbose > 2:
      print('execCommand: reading...')
  
  if settings.debug > 2:
    print(f"execCommand: {alldata}")
  return(alldata)  

## ------------------------------------------------------------------

# return True if platform or id/hostname is excluded (Wireless controller, AP, etc.)

async def excludedDevices(id, ip, platform):

  if ( 'UCS-' in platform.upper() 
    or 'AIR-' in platform.upper() 
    or 'PHONE' in platform.upper()  
    or 'LINUX' in platform.upper() ):
    #or 'PROD' in id.upper() ):   # exclude some devices in id.upper()
    return True
       
  return False    
   
## ------------------------------------------------------------------
# parse command 'show LLDP neighbors detail' in cisco getting IP, name, platform
# returns a list of objects

async def parseLLDP(data):

  ip='-' 
  id='-' 
  platform='-'
  devicesFound = []   # list of LLDP neighbors detected, with name and IP
  
  try:
  
    if (data is not None and len(data) > 10):
      for line in (data.decode('utf-8')).splitlines():
        if settings.debug > 2:
          print(f"parseLLDP line: {line}")

        if ( ' PHONE ' in line.upper() or ' CAMERA ' in line.upper() ):
          continue

        if ( 'SYSTEM NAME:' in line.upper() ):
          ip='-' 
          id='-' 
          platform='-'
          id = ( (line.split(':')[1]).split('.')[0].strip() )

        if ( 'CISCO IOS ' in line.upper() ):
          platform = line.strip()[0:50]
 
        if ( 'IP:' in line ):
          ip = ( (line.split(':')[1]).strip() )

          if  len(ip) > 3 and len(platform) > 3 and len(id) > 1:
            if not await(excludedDevices(id, ip, platform)):
              device = {'name' : id,'ip': ip}
              if  not device in devicesFound and len(ip) > 3:
                devicesFound.append(device)

  except Exception as e:  
    print ("Exception:::", e)
    print("parseLLDP Exception (e: {} data: {})".format(e, data))
    logging.info("parseLLDP Exception (e: {} data: {})".format(e, data))

  if settings.verbose > 2:
    print(f"parseLLDP: {devicesFound}")  

  return(devicesFound)

## ------------------------------------------------------------------

# parse command 'show cdp neighbors' in cisco getting IP, name, platform
# returns a list of objects

async def parseCDP(data):

  ip='-' 
  id='-' 
  platform='-'
  devicesFound = []   # list of CDP neighbors detected, with name and IP
  
  try:
    if (data is not None and len(data) > 10):
      for line in (data.decode('utf-8')).splitlines():
        if settings.debug > 2:
          print(f"parseCDP: {line}")

        if ( 'Device ID:' in line ):
          ip='-' 
          id='-' 
          platform='-'
          id = ( (line.split(':')[1]).split('.')[0].strip() )
 
        if ( 'Platform:' in line ):
          platform = ( (line.split(':')[1]).split(',')[0].strip() )

        if ( 'IP address:' in line ):
          ip = ( (line.split(':')[1]).strip() )

        # build info for previus device, then get data for this (new) one
        ## TODO TODO: make dynamic list for exclusions, maybe from DB
        
        #if settings.verbose > 0:
        #  print (f"parseCDP IP: {ip}  Platform: {platform}   ID:  {id}" )
        if  len(ip) > 3 and len(platform) > 3 and len(id) > 1:
          if not await(excludedDevices(id, ip, platform)):
            device = {'name' : id,'ip': ip}
            if  not device in devicesFound and len(ip) > 3:
              devicesFound.append(device)

  except Exception as e:  
    print (f"parseCDP Exception:::  {e}")
    print("parseCDP Exception (e: {} data: {})".format(e, data))
    logging.info("parseCDP Exception (e: {} data: {})".format(e, data))

  if settings.verbose > 2:
    print(f"parseCDP: {devicesFound}")  
  return(devicesFound)

## ------------------------------------------------------------------

## parse 'show version' ciaco command response
async def processShowVer(data):

  serialNum = '-'
  hostname = '-'
  uptime = '-'
  platform = '-'
  platformV1 = None
  platformV2 = None
  
  try:
    if data is not None:
      for line in (data.decode('utf-8')).splitlines():
        if settings.debug > 2:
          print(f"processShowVer: {line}")
        if ( ' BOARD ID ' in line.upper() ):
          serialNum = line.strip().split(' ')[-1]
        if ( ' uptime ' in line ):
          hostname = line.strip().split('uptime')[0].strip()
          uptime = line.strip().split('uptime is')[-1].strip()
        
        ## get platform (different for 4500, 9200, 9500, 2960)
      
        if ( 'MODEL NUMBER' in line.upper() ):
          platformV1 = line.strip().split(':')[1].strip()
  #      if ( 'PHYSICAL MEMORY' in line.upper() or ( 'PROCESSOR' in line.upper() and ' OF ' in line.upper() and 'MEMORY' in line.upper()) ):
        if ( ( 'PROCESSOR' in line.upper() and ' OF ' in line.upper() and 'MEMORY' in line.upper()) ):
          platformV2 = line.strip().split('(')[0].strip()
        
  except Exception as e:  
    print (f"processShowVer Exception::: {e}")
    print("processShowVer Exception (e: {} data: {})".format(e, data))
    logging.info("processShowVer Exception (e: {} data: {})".format(e, data))
       
  if (platformV1 is not None):
    platform = platformV1
  if (platformV2 is not None):
    platform = platformV2
  
  if settings.verbose > 2:
    print(f"processShowVer serial {serialNum}  hostname {hostname}  Uptime: {uptime}   Platform: {platform}"   )
  return( (serialNum, hostname, uptime, platform) )   

## ------------------------------------------------------------------

#  show interfaces format for switches:
# Port      Name               Status       Vlan       Duplex  Speed Type
# Te1/1/1   DC_VSS-PEER-LINK S connected    trunk        full  a-10G 10GBase-LR
# Te1/1/2   DC_VSS-PEER-LINK S connected    trunk        full  a-10G 10GBase-LR
# Te1/1/3   Prod FW #1 Port 13 connected    143          full  a-10G 10GBase-LR
# Gi1/0/19  Caster Overhead Ru connected    35         a-full  a-100 10/100/1000BaseTX
# Gi1/0/20  CCM pulpit camera  connected    35         a-full  a-100 10/100/1000BaseTX
# Gi1/0/21                     notconnect   999          auto   auto 10/100/1000BaseTX
# Gi1/0/22                     notconnect   999          auto   auto 10/100/1000BaseTX
# Gi1/0/23                     notconnect   999          auto   auto 10/100/1000BaseTX

# as lines length is variable we need to use title line to detect parsing positions

async def processIFACE(data, deviceID, switchName, switchIP, serialNum):

  iFaceList = []   # list of Interfaces addresses
  iFaceEntry = None
  
  (portPOS, descrPOS, statusPOS, vlanPOS, duplexPOS, speedPOS, itypePos) = (-1,-1,-1,-1,-1,-1,-1)
  
  try:
    if (data is not None and len(data) > 10):
      for line in (data.decode('utf-8')).splitlines():

        if settings.debug > 2:
          print(f"processIFACE: {line}")
    
        port='-'
        descr='-' 
        status='-' 
        duplex='-' 
        speed='-'
        itype='-'
        vlan='-' 
        vlanNum='-'
     
        # Port      Name               Status       Vlan       Duplex  Speed Type
    
        if ( 'PORT' in line.upper() and 'STATUS' in line.upper()):  # title line, get positions
          portPOS = line.upper().find('PORT')
          descrPOS = line.upper().find('NAME')
          statusPOS = line.upper().find('STATUS')
          vlanPOS = line.upper().find('VLAN')
          duplexPOS = line.upper().find('DUPLEX')
          speedPOS = line.upper().find('SPEED')
          itypePos = line.upper().find('TYPE')
        else:                                    # rest of lines of interest
          if len(line) >= 50:

            if (portPOS > -1 and descrPOS > -1):
              port = line[portPOS:descrPOS].strip()
            if (descrPOS > -1 and statusPOS > -1):
              descr = line[descrPOS:statusPOS].strip()
            if (statusPOS > -1 and vlanPOS > -1):
              status = line[statusPOS:vlanPOS].strip()
            if (vlanPOS > -1 and duplexPOS > -1):
              vlan = line[vlanPOS:duplexPOS].strip()
            if (duplexPOS > -1 and speedPOS > -1):
              duplex = line[duplexPOS:speedPOS].strip()
            if (speedPOS > -1 and itypePos > -1):
              speed = line[speedPOS:itypePos].strip()
            if (itypePos > -1):
              itype = line[itypePos:].strip()
          
            try:
              vlanNum = int(vlan)
            except ValueError:
              vlanNum = -1
              
            if (len(port)>1):  
              iFaceEntry = {'id': deviceID, 'port': port, 'descr': descr, 'status': status, 'vlan': vlan, 'vlanNum': vlanNum, 'duplex': duplex, 'speed': speed, 'type': itype}
              
              if settings.verbose > 2:
                 print(f"iFaceEntry: {iFaceEntry}")

            if  not iFaceEntry in iFaceList:
              iFaceList.append(iFaceEntry)
       
  except Exception as e:  
    print (f"processIFACE: Exception::: {e}")
    print("processIFACE Exception (e: {} data: {})".format(e, data))
    logging.info("processIFACE Exception (e: {} data: {})".format(e, data))

  if settings.verbose > 2:
    print (f"processIFACE List: {iFaceList}")

  return(iFaceList)

## ------------------------------------------------------------------

#show int | i (protoc|error|ut rate)

#Ethernet7/3 is up, line protocol is up (connected)
#  5 minute input rate 0 bits/sec, 0 packets/sec
#  5 minute output rate 0 bits/sec, 0 packets/sec
#     0 input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored
#     0 output errors, 0 collisions, 0 interface resets

async def processIntErrors(data, deviceID, switchName, switchIP, serialNum):

  iFaceErrorList = []   # list of Interfaces addresses
  iFaceEntry = None
  
  try:
    if (data is not None and len(data) > 10):

      interfaceName='-' 
      inputErrors='-' 
      outputErrors='-' 
      inputRate='-' 
      outputRate='-'           
      crcErrors='-' 
      collisionErrors='-'         

      for line in (data.decode('utf-8')).splitlines():  

        if settings.debug > 2:
          print(f"processIntErrors: {line}")

        if ( 'LINE PROTOCOL' in line.upper() ):
          interfaceName = ( (line.split(',')[0]).split(' ')[0].strip() )
          if settings.debug > 2:         
            print(f"processIntErrors interfaceName: {interfaceName}")

        if ( 'INPUT RATE' in line.upper() ):
          inputRate = ( (line.split(',')[0]).strip().split(' ')[4] )
          if settings.debug > 2:         
            print(f"processIntErrors inputRate: {inputRate}")

        if ( 'OUTPUT RATE' in line.upper() ):
          outputRate = ( (line.split(',')[0]).strip().split(' ')[4] )
          if settings.debug > 2:         
            print(f"processIntErrors outputRate: {outputRate}")

        if ( 'INPUT ERRORS' in line.upper() ):
          inputErrors = ( (line.split(',')[0]).strip().split(' ')[0] )
          crcErrors = ( (line.split(',')[1]).strip().split(' ')[0] )
          if settings.debug > 2:         
            print(f"processIntErrors inputErrors: {inputErrors}")
            print(f"processIntErrors crcErrors: {crcErrors}")

        if ( 'OUTPUT ERRORS' in line.upper() ):
          outputErrors = ( (line.split(',')[0]).strip().split(' ')[0] )
          collisionErrors = ( (line.split(',')[1]).strip().split(' ')[0] )
          if settings.debug > 2:       
            print(f"processIntErrors outputErrors: {outputErrors}")
            print(f"processIntErrors collisionErrors: {collisionErrors}")

          if (len(interfaceName)>1):  
            iFaceErrorEntry = {'id': deviceID, 'interfaceName': interfaceName, 'inputRate': inputRate, 'outputRate': outputRate, 'inputErrors': inputErrors, 'outputErrors': outputErrors, 'crcErrors': crcErrors, 'collisionErrors': collisionErrors}
            if settings.verbose > 2:  
              print(f"processIntErrors entry {iFaceErrorEntry}")       

            if  not iFaceErrorEntry in iFaceErrorList:
              iFaceErrorList.append(iFaceErrorEntry)
              interfaceName='-' 
              inputErrors='-' 
              outputErrors='-' 
              inputRate='-' 
              outputRate='-'           
              crcErrors='-' 
              collisionErrors='-'    

  except Exception as e:  
    print (f"processIntErrors Exception::: {e}")
    print("processIntErrors Exception (e: {} data: {})".format(e, data))
    logging.info("processIntErrors Exception (e: {} data: {})".format(e, data))
           
  if settings.verbose > 1:  
    print(f"processIntErrors list {iFaceErrorList}")       
    
  return(iFaceErrorList)

## ------------------------------------------------------------------

#
#  MAC address format for switches (A):
# vlan     mac address     type        protocols               port
#---------+---------------+--------+---------------------+-------------------------
#   2      0008.e3ff.fd90    static ip,ipx,assigned,other Switch
#   2      000b.dc00.3b07   dynamic ip,ipx,assigned,other Port-channel11
#
#  MAC address format for switches (B):
#Vlan    Mac Address       Type        Ports
#----    -----------       --------    -----
# All    0100.0ccc.cccc    STATIC      CPU
# All    0100.0ccc.cccd    STATIC      CPU
#

async def processMAC(data, deviceID, switchName, switchIP, serialNum):

  macList = []   # list of MAC addresses
   
  multicastEntries = False 

  try:
  
    if (data is not None and len(data) > 10):
      for line in (data.decode('utf-8')).splitlines():
    
        if settings.debug > 2:
          print(f"processMAC: {line}")

        if multicastEntries:
          continue
        else: 
          line = re.sub('\s{2,}', ' ', line)
          etype='-' 
          vlan='-' 
          mac='-'
          vlanNum=-1
          port='-'
    
          if len(line) >= 20:
            if ( 'STATIC' in line.upper() or  'DYNAMIC' in line.upper() ):

              fields = line.split()
 
              vlan = fields[0].strip().replace(" ","").upper()
              vlanNum = x = int(vlan) if (vlan).isdigit() else -1
              mac = fields[1].replace(':','').replace('.','').strip()
              etype = fields[2].strip()
        
              if (len(fields) > 4):
                port = fields[4].strip()    # format A   above
              else:
                port = fields[3].strip()    # format B   above 
        
              if (len(mac)>8):  
                macEntry = {'id': deviceID, 'mac': mac, 'vlanNum':vlanNum, 'type': etype, 'port': port}
              if settings.verbose > 2:
                print(f"processMAC entry: {macEntry}")
              if  not macEntry in macList:
                macList.append(macEntry)

        if ( 'Multicast Entries' in line ):   # we stop gathering data as soon as we detect one line indicating the following info is fo multicast
          multicastEntries = True 
       
  except Exception as e:  
    print (f"processMAC Exception::: {e}")
    print("processMAC Exception (e: {} data: {})".format(e, data))
    logging.info("processMAC Exception (e: {} data: {})".format(e, data))
 
  if settings.verbose > 2:
    print(f"processMAC List: {macList}")

  return(macList)

## ------------------------------------------------------------------

async def processARP(data, deviceID, switchName, switchIP, serialNum):

  arpList = []   # list of IP-MAC pairs

  try:
    if (data is not None and len(data) > 10):
      for line in (data.decode('utf-8')).splitlines():

        myStr = re.sub('\s{2,}', ' ', line)
        ip='-' 
        age='-' 
        vlan='-' 
        mac='-'
        vlanNum=-1
        data = myStr.split()
        if len(data) >= 6:
          vlan = data[5].strip().replace(" ","").upper()
          vlanNum = x = int(vlan[4:]) if (vlan[4:]).isdigit() else -1
        if len(data) >= 4:
          ip = data[1]
          age = data[2].strip()
          mac = data[3].replace(':','').replace('.','')
        
        if (len(mac)>8):  
          if settings.verbose > 2:
            print("""processARP: ID: {} serialNum:{} switch IP:{} switch name: {}  ip: {} mac:{} vlan:{}""".format(deviceID, serialNum, switchIP, switchName, ip, mac, vlanNum )) 

          arpEntry = {'id': deviceID, 'serialNum' : serialNum, 'switchIP': switchIP, 'switchName': switchName, 'ip': ip, 'mac': mac, 'vlanNum':vlanNum, 'age': age}
          if  not arpEntry in arpList and len(ip) > 3:
            arpList.append(arpEntry)
 
  except Exception as e:  
    print (f"processARP Exception::: {e}")
    print("processARP Exception (e: {} data: {})".format(e, data))
    logging.info("processARP Exception (e: {} data: {})".format(e, data))

  if settings.verbose > 2:
    print (f"processARP list: {arpList}")

  return(arpList)

## ------------------------------------------------------------------
## ------------------------------------------------------------------
