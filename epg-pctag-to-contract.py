################################################################################
# Authors: Zsombor Szira            #
#                                                                              #
#                                                                              #
# Oct 2019                                                                     #
#                                                                              #
# Takes an input json config of a tenant, that can be obtained by "Saving as"  #
#   from the APIC GUI. It produces a csv to show Contract usage                #
#     - BDs with SVIs and L3outs for each VRF                                  #
#     - Contracts and connected EPGs/L3outs                                    #
#     - supporting text, incl. EPG to interface and L3out static routes        #
#                                                                              #
################################################################################

import json
import csv
import sys
from six import iteritems

json_filename = '/home/zombi/Downloads/tn-DDE-RAT-08042020.json'
csv_filename = '/home/zombi/Downloads/tn-DDE-RAT-08042020.csv'

unique_keys = set()

def _nested_lookup(key, document):
    """Lookup a key in a nested document, yield a value"""
    if isinstance(document, list):
        for d in document:
            for result in _nested_lookup(key, d):
                yield result

    if isinstance(document, dict):
        for k, v in iteritems(document):
            if k == key:
                yield v
            elif isinstance(v, dict):
                for result in _nested_lookup(key, v):
                    yield result
            elif isinstance(v, list):
                for d in v:
                    for result in _nested_lookup(key, d):
                        yield result

# Find the BDs associated to a specific context
def getBdForCtx(bds, ctxName):
    ctxbds=[]
    for bd in bds:
        for child in bd['children']:
            if 'fvRsCtx' in child:
                if child['fvRsCtx']['attributes']['tnFvCtxName'] == ctxName:
                     ctxbds.append(bd['attributes']['name'])
    return ctxbds

# Find the L3outs associated to a specific context
def getL3outsForCtx(l3outs, ctxName):
    ctxl3outs=[]
    for l3out in l3outs:
        for child in l3out['children']:
            if 'l3extRsEctx' in child:
                if child['l3extRsEctx']['attributes']['tnFvCtxName'] == ctxName:
                    ctxl3outs.append(l3out['attributes']['name'])
    return ctxl3outs

# Gets the contracts consumed by a specific L3out
def getConsContractsL3out(l3out):
    contractlist = []
    for l3outchild in l3out['children']:
        if 'l3extInstP' in l3outchild:
            for child in l3outchild['l3extInstP']['children']:
                if 'fvRsCons' in child:
                    contractlist.append(child['fvRsCons']['attributes']['tnVzBrCPName'])
    return contractlist

# Gets the subnets announced by a specific L3out
def getExportSubnets(l3out):
    subnetlist = []
    for l3outchild in l3out['children']:
        if 'l3extInstP' in l3outchild:
            for child in l3outchild['l3extInstP']['children']:
                if 'l3extSubnet' in child:
                    if child['l3extSubnet']['attributes']['scope'] == 'export-rtctrl':
                        subnetlist.append(child['l3extSubnet']['attributes']['ip'])
    return subnetlist

# Gets the subnets imported by a specific L3out
def getImportSubnets(l3out):
    subnetlist = []
    for l3outchild in l3out['children']:
        if 'l3extInstP' in l3outchild:
            for child in l3outchild['l3extInstP']['children']:
                if 'l3extSubnet' in child:
                    if child['l3extSubnet']['attributes']['scope'] == 'import-security':
                        subnetlist.append(child['l3extSubnet']['attributes']['ip'])
    return subnetlist

# Get contracts consumed by an EPG
def getConsContractsforEPG (epg):
    contractlist = []
    for child in epg['children']:
        if 'fvRsCons' in child:
            contractlist.append(child['fvRsCons']['attributes']['tnVzBrCPName'])
    return contractlist

# Get contracts provided by an EPG
def getProvContractsforEPG (epg):
    contractlist = []
    for child in epg['children']:
        if 'fvRsProv' in child:
            contractlist.append(child['fvRsProv']['attributes']['tnVzBrCPName'])
    return contractlist

# Gets the BD name in an EPG
def getBdForEPG (epg_name):
    for child in epgs['children']:
        if 'fvRsBd' in child:
            return child['fvRsBd']['attributes']['tnFvBDName']

# Gets the IP addresses (subnets) defined in a BD
def getIpsForBD (bds, bd_name):
    ips=[]
    for bd in bds:
        if bd['attributes']['name'] == bd_name:
            for child in bd['children']:
                if 'fvSubnet' in child:
                    ips.append(child['fvSubnet']['attributes']['ip'])
    return ips

#Get EPGs consuming a contract
def getEPGForConsumeCont (contcons):
    consepg=[]
    for epg in fvAllEPG:
        for child in epg['children']:
            if 'fvRsCons' in child:
                if child['fvRsCons']['attributes']['tnVzBrCPName'] == contcons:
                    consepg.append(epg['attributes']['name'])
    return consepg

#Get EPGs providing a contract
def getEPGForProvideCont (contcons):
    provepg=[]
    for epg in fvAllEPG:
        for child in epg['children']:
            if 'fvRsProv' in child:
                if child['fvRsProv']['attributes']['tnVzBrCPName'] == contcons:
                    provepg.append(epg['attributes']['name'] + ' - ' + epg['attributes']['descr'])
    return provepg

#Get EPGs Providing or Consuming a contract
def getEPGForCont (contcons):
    usebyepg=[]
    for epg in fvAllEPG:
        for child in epg['children']:
            if 'fvRsProv' in child and child['fvRsProv']['attributes']['tnVzBrCPName'] == contcons:
                 usebyepg.append(epg['attributes']['name'])
            else:
                if 'fvRsCons' in child and child['fvRsCons']['attributes']['tnVzBrCPName'] == contcons:
                    usebyepg.append(epg['attributes']['name'])
    return list(set(usebyepg))

#Get L3outs Providing or Consuming a contract
def getL3outForCont (contcons):
    usebyl3out=[]
    for l3out in l3extOut:
        for l3outchild in l3out['children']:
            if 'l3extInstP' in l3outchild:
                for child in l3outchild['l3extInstP']['children']:
                    if 'fvRsCons' in child and child['fvRsCons']['attributes']['tnVzBrCPName'] == contcons:
                        usebyl3out.append(l3out['attributes']['name'])
                        usebyl3out.append(l3outchild['l3extInstP']['attributes']['name'])
                    else:
                        if 'fvRsProv' in child and child['fvRsProv']['attributes']['tnVzBrCPName'] == contcons:
                            usebyl3out.append(l3out['attributes']['name'])
                            usebyl3out.append(l3outchild['l3extInstP']['attributes']['name'])
    return list(set(usebyl3out))

# Get path for an EPG
def getPathEPG (epg):
    pathlist = []
    encaplist = []
    modelist = []
    for child in epg['children']:
        if 'fvRsPathAtt' in child:
            pathlist.append(child['fvRsPathAtt']['attributes']['tDn'])
            encaplist.append(child['fvRsPathAtt']['attributes']['encap'])
            modelist.append(child['fvRsPathAtt']['attributes']['mode'])
    matrix = []
    for i in range(len(pathlist)):
        matrix.append([pathlist[i] + '; ', encaplist[i] + '; ', modelist[i]])
    return matrix

# Get L3out and l3extInstP providing a contract
def getL3outProvContr (cont):
    usebyl3out = []
    usebyInstP = []
    for l3out in l3extOut:
        for l3outchild in l3out['children']:
            if 'l3extInstP' in l3outchild:
                for child in l3outchild['l3extInstP']['children']:
                    if 'fvRsProv' in child and child['fvRsProv']['attributes']['tnVzBrCPName'] == cont:
                        usebyl3out.append(l3out['attributes']['name'])
                        usebyInstP.append(l3outchild['l3extInstP']['attributes']['name'])
    matrix = []
    for i in range(len(usebyl3out)):
        matrix.append([usebyl3out[i] + '; ', usebyInstP[i]])
    return matrix

# Get L3out and l3extInstP consuming a contract
def getL3outConsContr (cont):
    usebyl3out = []
    usebyInstP = []
    for l3out in l3extOut:
        for l3outchild in l3out['children']:
            if 'l3extInstP' in l3outchild:
                for child in l3outchild['l3extInstP']['children']:
                    if 'fvRsCons' in child and child['fvRsCons']['attributes']['tnVzBrCPName'] == cont:
                        usebyl3out.append(l3out['attributes']['name'])
                        usebyInstP.append(l3outchild['l3extInstP']['attributes']['name'])
    matrix = []
    for i in range(len(usebyl3out)):
        matrix.append([usebyl3out[i] + '; ', usebyInstP[i]])
    return matrix


# Get subject for a contract
def getSubjectForContr (cont):
    subj = 0
    for contracts in vzBrCP:
        if contracts['attributes']['name'] == cont:
            for child in contracts['children']:
                if 'vzSubj' in child:
                    subj = (child['vzSubj']['attributes']['name'])
    return subj

# Get filter for a contract
def getFilterForContr (cont):
    filt = 0
    for contracts in vzBrCP:
        if contracts['attributes']['name'] == cont:
            for child in contracts['children']:
                if 'vzSubj' in child:
                    for child2 in child['vzSubj']['children']:
                        if 'vzRsSubjFiltAtt' in child2:
                            filt = child2['vzRsSubjFiltAtt']['attributes']['tnVzFilterName']
    return filt

# Get service graph for a contract
def getSGForContr (cont):
    sg = 'NA'
    for contracts in vzBrCP:
        if contracts['attributes']['name'] == cont:
            for child in contracts['children']:
                if 'vzSubj' in child:
                    for child2 in child['vzSubj']['children']:
                        if 'vzRsSubjGraphAtt' in child2:
                            sg = child2['vzRsSubjGraphAtt']['attributes']['tnVnsAbsGraphName']
    return sg

# Get scope for a contract
def getScopeForContr (cont):
    scope = 0
    for contracts in vzBrCP:
        if contracts['attributes']['name'] == cont:
            scope = (contracts['attributes']['scope'])
    return scope



# Load the config file in a dictionary
with open(json_filename) as fd:
    config = json.load(fd)
    fd.close()

# Strip off the initial metadata labels, find out the tenant name
fvTenant = config['imdata'][0]['fvTenant']


# Some lists with JSON code, to make things easier
fvAp = []
fvCtx = []
l3extOut = []
fvBD = []
vzBrCP = []
fvAllEPG = []


# Get the list of ANPs, this returns a list so I need to go trough it again.
# To create the document in order I need to divide the objects depending on their class
for child in fvTenant['children']:
    if 'fvAp' in child:
        fvAp.append(child['fvAp'])
    if 'fvCtx' in child:
        fvCtx.append(child['fvCtx'])
    if 'l3extOut' in child:
        l3extOut.append(child['l3extOut'])
    if 'fvBD' in child:
        fvBD.append(child['fvBD'])
    if 'vzBrCP' in child:
        vzBrCP.append(child['vzBrCP'])
for anp in fvAp:
    for child in anp['children']:
         if 'fvAEPg' in child:
            fvAllEPG.append(child['fvAEPg'])


# clear csv
csvFile = open(csv_filename, "w")
csvFile.truncate()
csvFile.close()

# create csv header
csv_header = ['Type', 'Name', 'Network/BD', 'pctag', 'Direction', 'Contract', 'Scope', 'Subject', 'Filter', 'Service graph']
with open(csv_filename, 'a') as csvFile:
    writer = csv.writer(csvFile)
    writer.writerow(csv_header)
csvFile.close()

# fill csv with epg data
for epgs in fvAllEPG:
    row = []
    epg_name = epgs['attributes']['name']
    pctag = epgs['attributes']['pcTag']
    for child in epgs['children']:
        if 'fvRsProv' in child:
            row.append('EPG')
            row.append(epg_name)
            BD = 0
            BD = getBdForEPG(epg_name)
            row.append(BD)
            row.append(pctag)
            row.append('Provide')
            contract = 0
            contract = child['fvRsProv']['attributes']['tnVzBrCPName']
            row.append(contract)
            Scope = 0
            Scope = getScopeForContr(contract)
            row.append(Scope)
            Subject = 0
            Subject = getSubjectForContr(contract)
            row.append(Subject)
            Filter = 0
            Filter = getFilterForContr(contract)
            row.append(Filter)
            ServiceGraph = 0
            ServiceGraph = getSGForContr(contract)
            row.append(ServiceGraph)
            with open(csv_filename, 'a') as csvFile:
                writer = csv.writer(csvFile)
                writer.writerow(row)
            csvFile.close()
            row = []
        if 'fvRsCons' in child:
            row.append('EPG')
            row.append(epg_name)
            BD = 0
            BD = getBdForEPG(epg_name)
            row.append(BD)
            row.append(pctag)
            row.append('Consume')
            contract = 0
            contract = child['fvRsCons']['attributes']['tnVzBrCPName']
            row.append(contract)
            Scope = 0
            Scope = getScopeForContr(contract)
            row.append(Scope)
            Subject = 0
            Subject = getSubjectForContr(contract)
            row.append(Subject)
            Filter = 0
            Filter = getFilterForContr(contract)
            row.append(Filter)
            ServiceGraph = 0
            ServiceGraph = getSGForContr(contract)
            row.append(ServiceGraph)
            with open(csv_filename, 'a') as csvFile:
                writer = csv.writer(csvFile)
                writer.writerow(row)
            csvFile.close()
            row = []

for l3out in l3extOut:
    row = []
    l3out_name = l3out['attributes']['name']
    for l3outchild in l3out['children']:
        if 'l3extInstP' in l3outchild:
            for child in l3outchild['l3extInstP']['children']:
                if 'fvRsProv' in child:
                    row.append('L3out')
                    row.append(l3out_name)
                    network = l3outchild['l3extInstP']['attributes']['name']
                    row.append(network)
                    row.append(l3outchild['l3extInstP']['attributes']['pcTag'])
                    row.append('Provide')
                    contract = 0
                    contract = child['fvRsProv']['attributes']['tnVzBrCPName']
                    row.append(contract)
                    Scope = 0
                    Scope = getScopeForContr(contract)
                    row.append(Scope)
                    Subject = 0
                    Subject = getSubjectForContr(contract)
                    row.append(Subject)
                    Filter = 0
                    Filter = getFilterForContr(contract)
                    row.append(Filter)
                    ServiceGraph = 0
                    ServiceGraph = getSGForContr(contract)
                    row.append(ServiceGraph)
                    with open(csv_filename, 'a') as csvFile:
                        writer = csv.writer(csvFile)
                        writer.writerow(row)
                    csvFile.close()
                    row = []
                if 'fvRsCons' in child:
                    row.append('L3out')
                    row.append(l3out_name)
                    network = l3outchild['l3extInstP']['attributes']['name']
                    row.append(network)
                    row.append(l3outchild['l3extInstP']['attributes']['pcTag'])
                    row.append('Consume')
                    contract = 0
                    contract = child['fvRsCons']['attributes']['tnVzBrCPName']
                    row.append(contract)
                    Scope = 0
                    Scope = getScopeForContr(contract)
                    row.append(Scope)
                    Subject = 0
                    Subject = getSubjectForContr(contract)
                    row.append(Subject)
                    Filter = 0
                    Filter = getFilterForContr(contract)
                    row.append(Filter)
                    ServiceGraph = 0
                    ServiceGraph = getSGForContr(contract)
                    row.append(ServiceGraph)
                    with open(csv_filename, 'a') as csvFile:
                        writer = csv.writer(csvFile)
                        writer.writerow(row)
                    csvFile.close()
                    row = []

print ("Saving document...")
