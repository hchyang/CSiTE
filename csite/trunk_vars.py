#!/usr/bin/env python3

#########################################################################
# Author: Hechuan Yang
# Created Time: 2017-04-20 10:10:59
# File Name: trunk_vars.py
# Description: 
#########################################################################

import logging
import copy as cp

def classify_vars(vars_file,chroms_cfg,leaves_number,tree):
    '''
    There should be at least 5 columns for each varians in the input file,
    The 6th column is optional.
    chr:      the chromosome of the variants
    hap:      which halotype of the chromosome the variant locates in (0 based).
              It depends on the parental of the chromosome. If the parental is '011',
              then there are 3 haplotypes: 0,1,2
    start:    the start of the variant
    end:      the end of the variant
    var:      an integer. 0/1/2: SNV, -1: deletion, +int: amplification
    bearer:   optional. an integer of some integers separeted by comma (only for SNV). 
              0 (or without this column): the SNV is on the original copy
              N: the SNV is on the copy N of this segment
    P.S. start and end are 0 based. And the region of each var is like in bed: [start,end).
    '''
    snvs={}
    amps={}
    dels={}
    cnvs={}

#classify vars into different categories
    with open(vars_file) as f:
        for line in f:
            if line.startswith('#'):
                continue
            cols=line.split()
            if len(cols)==5:
                chroms,hap,start,end,var=cols
                bearer=0
            elif len(cols)==6:
                chroms,hap,start,end,var,bearer=cols
                if var not in ('0','1','2'):
                    raise TrunkVarError('Only the record of SNV can have the bearer (6th) column.'+
                        'Check the record below:\n{}'.format(line))
            else:
                raise TrunkVarError('There should be 5 or 6 columns in your --trunk_vars file.\n'+
                    'Check the record below:\n{}'.format(line))

            hap=int(hap)
            start=int(start)
            end=int(end)
            if chroms not in chroms_cfg['order']:
                raise TrunkVarError('The chr of the variant below is not in the genome:\n{}'.format(line))
            if not 0<=hap<len(chroms_cfg[chroms]['parental']):
                raise TrunkVarError('The haplotype of the variant below is out of range:\n{}'.format(line))
            if not (0<=start<chroms_cfg[chroms]['length'] and 0<=end<chroms_cfg[chroms]['length']): 
                raise TrunkVarError('The coordinant of the variant below is out of range:\n{}'.format(line))
            if not start<end: 
                raise TrunkVarError('The start of the variant should be less than its end :\n{}'.format(line))

            if var.startswith('+') or var.startswith('-'):
                copy=int(var)
                if chroms not in cnvs:
                    cnvs[chroms]={}
                if hap not in cnvs[chroms]:
                    cnvs[chroms][hap]=[]
#construct cnv
                cnvs[chroms][hap].append({'seg': [0,chroms_cfg[chroms]['length']],
                                         'start': start,
                                         'end': end,
                                         'copy': copy,
                                         'leaves_count': leaves_number,
                                         'pre_snvs': [],
                                         'new_copies': [],
                                        })

                if copy==-1:
                    cnvs[chroms][hap][-1]['type']='DEL'
                    if chroms not in dels:
                        dels[chroms]={}
                    if hap not in dels[chroms]:
                        dels[chroms][hap]=[]
                    dels[chroms][hap].append([start,end,copy])
                elif copy>0:
                    cnvs[chroms][hap][-1]['type']='AMP'
                    if chroms not in amps:
                        amps[chroms]={}
                    if hap not in amps[chroms]:
                        amps[chroms][hap]=[]
                    amps[chroms][hap].append([start,end,copy])
                    for i in range(copy):
                        segment=cp.deepcopy(tree)
                        cnvs[chroms][hap][-1]['new_copies'].append(segment)
                else:
#right now, copy must be -1 or a positive integer
                    raise TrunkVarError('The fourth column of the variant below is invalid:\n{}'.format(line))
            else:
                if end-start!=1:
                    raise TrunkVarError('The coordinant of the SNV below is not correct:\n{}'.format(line))
                if var not in ('0','1','2'):
                    raise TrunkVarError('The mutation form of the SNV below is not correct:\n{}'.format(line))
                form=int(var)
                if chroms not in snvs:
                    snvs[chroms]={}
                if hap not in snvs[chroms]:
                    snvs[chroms][hap]=[]
                snvs[chroms][hap].append({'type':'SNV',
                                         'start':start,
                                         'end':end,
                                         'mutation':form,
                                         'bearer':bearer
                                        })

    check_vars(snvs,amps,dels)
    
    logging.debug('trunk SNVs:%s',snvs)
    logging.debug('trunk AMPs:%s',amps)
    logging.debug('trunk DELs:%s',dels)
    logging.debug('trunk CNVs:%s',cnvs)
    return snvs,cnvs

def check_vars(snvs,amps,dels):
    '''
    Check: whether any snv/amp overlap with deletion.
    '''
    for chroms in sorted(dels.keys()):
        snvs_chroms=snvs.get(chroms,{})
        amps_chroms=amps.get(chroms,{})
        for hap in sorted(dels[chroms].keys()):
            snvs_chrom_hap=snvs_chroms.get(hap,[])
            amps_chrom_hap=amps_chroms.get(hap,[])
            for i in range(len(dels[chroms][hap])):
#on each haplotype, there shouldn't be SNV/AMP overlap with DEL
#on each haplotype, there shouldn't be AMP overlap with AMP
#on each haplotype, there shouldn't be DEL overlap with DEL
                deletion=dels[chroms][hap][i]
                for snv in snvs_chrom_hap:
                    if deletion[0]<=snv['start']<deletion[1]:
                        raise TrunkVarError('These variants below are in conflict with each other:\n'+
                            '{}\n'.format('\t'.join([str(x) for x in [chroms,hap,snv['start'],snv['end'],snv['mutation']]]))+
                            '{}\n'.format('\t'.join([str(x) for x in [chroms,hap,deletion[0],deletion[1],'-1']])))
                for amp in amps_chrom_hap:
                    if deletion[0]<=amp[0]<deletion[1] or deletion[0]<amp[1]<=deletion[1]:
                        raise TrunkVarError('These variants below are in conflict with each other:\n'+
                            '{}\n'.format('\t'.join([str(x) for x in [chroms,hap,amp[0],amp[1],'+'+str(amp[2])]]))+
                            '{}\n'.format('\t'.join([str(x) for x in [chroms,hap,deletion[0],deletion[1],'-1']])))
                if i<len(dels[chroms][hap])-1:
                    for deletion2 in dels[chroms][hap][i+1:]:
                        if deletion[0]<=deletion2[0]<deletion[1] or deletion[0]<deletion2[1]<=deletion[1]:
                            raise TrunkVarError('These variants below are in conflict with each other:\n'+
                                '{}\n'.format('\t'.join([str(x) for x in [chroms,hap,deletion2[0],deletion2[1],'-1']]))+
                                '{}\n'.format('\t'.join([str(x) for x in [chroms,hap,deletion[0],deletion[1],'-1']])))

class TrunkVarError(Exception):
    pass

