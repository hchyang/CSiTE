#!/usr/bin/env python3

#########################################################################
# Author: Hechuan Yang
# Created Time: 2017-04-04 18:00:34
# File Name: allinone.py
# Description:
#########################################################################

import sys
import os
import shutil
import argparse
import numpy
import yaml
import logging
import subprocess
import pyfaidx
from psite.vcf2fa import check_sex,check_vcf,check_autosomes
from psite.phylovar import check_prune,check_seed,check_purity,random_int,check_config_file
from psite.fa2wgs import check_depth,check_file
from psite.fa2wes import TargetAction, RATIO_WESSIM, RATIO_CAPGEM, check_program, check_snakemake

#handle the error below
#python | head == IOError: [Errno 32] Broken pipe
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE,SIG_DFL)

def main(progname=None):
    parser=argparse.ArgumentParser(
        description='an all-in-one wrapper for NGS reads simulation for tumor samples',
        prog=progname if progname else sys.argv[0])
    group0=parser.add_argument_group('Global arguments')
    group1=parser.add_argument_group('Module vcf2fa arguments')
    group2=parser.add_argument_group('Module phylovar arguments')
    group0.add_argument('-o','--output',type=str,required=True,metavar='DIR',
        help='output directory')
    group1.add_argument('-v','--vcf',type=check_vcf,required=True,metavar='FILE',
        help='a vcf file contains germline variants')
    group1.add_argument('-r','--reference',type=check_file,required=True,metavar='FILE',
        help='a fasta file of the reference genome')
    group2.add_argument('-t','--tree',type=check_file,required=True,metavar='FILE',
        help='a newick file contains ONE tree')
    group2.add_argument('-c','--config',type=check_file,required=True,metavar='FILE',
        help='a YAML file which contains the configuration of somatic variant simulation')
    group1.add_argument('-a','--autosomes',type=check_autosomes,required=True,metavar='STR',
        help='autosomes of the genome (e.g. 1,2,3,4,5 or 1..4,5)')
    default=None
    group2.add_argument('--affiliation',type=check_file,default=default,metavar='FILE',
        help='a file containing sector affiliation of the cells in the sample [{}]'.format(default))
    default=None
    group2.add_argument('--cnvl_dist',type=check_file,default=default,metavar='FILE',
        help="a file containing the distribution profile of CNVs' length [{}]".format(default))
    default='WGS'
    group0.add_argument('--type',type=str,default=default,choices=['WGS','WES','BOTH'],
        help='sequencing type to simulate [{}]'.format(default))
    default=1
    group0.add_argument('--cores',type=int,default=default,metavar='INT',
        help='number of cores used to run the program [{}]'.format(default))
    default=None
    group0.add_argument('--random_seed',type=check_seed,default=default,metavar='INT',
        help='the seed for random number generator (an integer between 0 and 2**31-1) [{}]'.format(default))
    default='allinone.log'
    group0.add_argument('--log',type=str,default=default,metavar='FILE',
        help='the log file to save the settings of each command [{}]'.format(default))
    default=1
    group0.add_argument('--start',type=int,default=default,choices=[1,2,3,4],
        help='the serial number of the module from which to start. \
            1: vcf2fa; 2: phylovar; 3: chain2fa; 4: fa2wgs/fa2wes [{}]'.format(default))
    default=None
    group1.add_argument('-s','--sex_chr',type=check_sex,default=default,metavar='STR',
        help='sex chromosomes of the genome (separated by comma) [{}]'.format(default))
    default=0.05
    group2.add_argument('-x','--prune',type=check_prune,default=default,metavar='FLOAT',
        help='trim all the children of the nodes with equal or less than this proportion of total leaves [{}]'.format(default))
    default=None
    group2.add_argument('--trunk_vars',type=str,default=default,metavar='FILE',
        help='a file containing truncal variants predefined by user [{}]'.format(default))
    default=0
    group2.add_argument('--trunk_length',type=float,default=default,metavar='FLOAT',
        help='the length of the trunk [{}]'.format(default))
    group3=parser.add_argument_group('Arguments for module fa2wgs/fa2wes')
    default=0.6
    group3.add_argument('-p','--purity',type=check_purity,default=default,metavar='FLOAT',
        help='the proportion of tumor cells in simulated tumor sample [{}]'.format(default))
    default=None
    group3.add_argument('--sectors',type=check_file,default=default,metavar='FILE',
        help='the file contains purity and depth profile of each tumor sector. \
              After this setting, -d/-p will be ignored. [{}]'.format(default))
    default=150
    group3.add_argument('--rlen',type=int,default=default,metavar='INT',
        help="the length of reads to simulate [{}]".format(default))
    group3.add_argument('--separate',action="store_true",
        help="keep each tip node's NGS reads file separately")
    group3.add_argument('--single',action="store_true",
        help="single cell mode. After this setting, the value of --tumor_depth/--tumor_rdepth \
            is the depth of each tumor cell (not the total depth of tumor sample anymore)")
    group4=parser.add_argument_group('Module fa2wgs arguments')
    default=50
    group4.add_argument('-d','--tumor_depth',type=check_depth,default=default,metavar='FLOAT',
        help='the mean depth of tumor sample for fa2wgs to simulate NGS reads [{}]'.format(default))
    default=0
    group4.add_argument('-D','--normal_depth',type=check_depth,default=default,metavar='FLOAT',
        help='the mean depth of normal sample for fa2wgs to simulate NGS reads [{}]'.format(default))
    default='art_illumina --noALN --quiet --paired --mflen 500 --sdev 20'
    group4.add_argument('--art',type=str,default=default,metavar='STR',
        help="the parameters for ART program ['{}']".format(default))
    group5=parser.add_argument_group('Module fa2wes arguments')
    default=None
    group5.add_argument('--probe',metavar='FILE',type=check_file,default=default,
        help='The file containing the probe sequences (FASTA format) [{}]'.format(default))
    default=None
    group5.add_argument('--target', metavar='FILE', type=str, default=default,
        help='The Target file containing the target regions (BED format)')
    default=0
    group5sub1=group5.add_mutually_exclusive_group()
    group5sub2=group5.add_mutually_exclusive_group()
    group5sub1.add_argument('--tumor_rdepth',type=check_depth,default=default,metavar='FLOAT',
        help='the mean depth of tumor sample for fa2wes to simulate NGS reads [{}]'.format(default))
    default=0
    group5sub1.add_argument('--tumor_rnum',metavar='INT',type=int,default=default,
        help='The number of short reads to simulate for tumor sample [{}]'.format(default))
    default=0
    group5sub2.add_argument('--normal_rdepth',type=check_depth,default=default,metavar='FLOAT',
        help='The mean depth of normal sample for fa2wes to simulate NGS reads [{}]'.format(default))
    default=0
    group5sub2.add_argument('--normal_rnum',metavar='INT',type=int,default=default,
        help='The number of short reads to simulate for normal sample [{}]'.format(default))
    default='wessim'
    group5.add_argument('--simulator', default=default, choices=['wessim','capgem'],
        action=TargetAction,
        help='The whole-exome sequencing simulator used for simulating short reads [{}]'.format(default))
    default = RATIO_WESSIM
    group5.add_argument('--ontarget_ratio', metavar='FLOAT', type=float, default=default,
        help='The percentage that simulated reads are expected to be from the target regions. \
            It is dependent on the simulator. The default value is {} for wessim and {} for \
            capgem [{}]'.format(RATIO_WESSIM, RATIO_CAPGEM, default))
    default=None
    group5.add_argument('--error_model',metavar='FILE',type=check_file, default=default,
        help='The file containing the empirical error model for NGS reads generated by GemErr \
            (It must be provided when capgem or wessim is used for simulation) [{}]'.format(default))
    default="snakemake --rerun-incomplete -k --latency-wait 120"
    group5.add_argument('--snakemake',metavar='STR', type=check_snakemake, default=default,
        help="The snakemake command used for calling a whole-exome sequencing simulator. \
            The Snakefile for a simulator is under the directory 'wes/config' of the source code. \
            Additional parameters for a simulator can be adjusted in the Snakefile ['{}']".format(default))
    default = 2
    group5.add_argument('--out_level', type=int, choices=[0, 1, 2], default=default,
        help="The level used to indicate how many intermediate output files are kept. \
            Level 0: keep all the files. \
            Level 1: keep files that are necessary for rerunning simulation \
                     ('config', 'genome_index', 'mapping', 'merged', and 'separate'). \
            Level 2: keep only final results ('merged' and 'separate') [{}]".format(default))

    args=parser.parse_args()
    if args.prune and args.single:
        raise argparse.ArgumentTypeError("Can not prune the tree in single cell mode! Set '--prune 0' if you want to simulate single cell data.")
    with open(args.config,'r') as configfile:
        config=yaml.safe_load(configfile)
    check_config_file(config=config)
    if args.type in ['WES','BOTH']:
        if args.probe==None:
            raise argparse.ArgumentTypeError("--probe is required to simulate WES data!")
        if args.target==None:
            raise argparse.ArgumentTypeError("--target is required to simulate WES data!")
        if args.tumor_rdepth!=0 and args.tumor_rnum!=0:
            raise argparse.ArgumentTypeError("--tumor_rdepth is not allowed to use together with --tumor_rnum!")
        if args.normal_rdepth!=0 and args.normal_rnum!=0:
            raise argparse.ArgumentTypeError("--normal_rdepth is not allowed to use together with --normal_rnum!")
        check_program(args.simulator)

#get absolute paths for the input files
    reference=os.path.abspath(args.reference)
    vcf=os.path.abspath(args.vcf)
    tree=os.path.abspath(args.tree)
    config=os.path.abspath(args.config)
    if args.trunk_vars:
        trunk_vars=os.path.abspath(args.trunk_vars)
    if args.affiliation:
        affiliation=os.path.abspath(args.affiliation)
    if args.cnvl_dist:
        cnvl_dist=os.path.abspath(args.cnvl_dist)
    if args.sectors:
        sectors=os.path.abspath(args.sectors)
    outdir=args.output
    if args.start==1:
        try:
            os.mkdir(outdir,mode=0o755)
        except FileExistsError as e:
            raise OutputExistsError("'{}' already exists. Try another directory to output! (-o/--output)".format(outdir)) from e
    else:
        assert os.path.isdir(outdir),"Couldn't start from step {}, ".format(args.start)+\
            "because I can not find the directory of previous results: '{}'.".format(outdir)
    os.chdir(outdir)

###### logging and random seed setting
    logging.basicConfig(filename=args.log if args.start==1 else args.log+'.start'+str(args.start),
        filemode='w',format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%m-%d %H:%M:%S',level='INFO')
    argv_copy=sys.argv[:]
    if '--art' in argv_copy:
        art_index=argv_copy.index('--art')
        argv_copy[art_index+1]="'{}'".format(argv_copy[art_index+1])
    if '--snakemake' in argv_copy:
        snakemake_index=argv_copy.index('--snakemake')
        argv_copy[snakemake_index+1]="'{}'".format(argv_copy[snakemake_index+1])
    argv_copy.insert(1,'allinone')
    logging.info(' Command: %s',' '.join(argv_copy))

    if args.random_seed==None:
        seed=random_int()
    else:
        seed=args.random_seed
    logging.info(' Random seed: %s',seed)
    numpy.random.seed(seed)

#subfolders
    normal_fa='normal_fa'
    tumor_fa='tumor_fa'
    tumor_chain='tumor_chain'
#map file
    map_dir='map'

#vcf2fa
    if args.start<2:
        cmd_params=[sys.argv[0],'vcf2fa',
                    '--vcf',vcf,
                    '--reference',reference,
                    '--output',normal_fa,
                    '--autosomes',args.autosomes]
        if args.sex_chr:
            cmd_params.extend(['--sex_chr',args.sex_chr])
        logging.info(' Command: %s',' '.join(cmd_params))
        subprocess.run(args=cmd_params,check=True)

#phylovar
#I place random_int() here as I do not want to skip it in any situation.
#Without this, you can not replicate the result with different --start setting.
    random_n=random_int()
    if args.start<3:
        if os.path.isdir(tumor_chain):
            shutil.rmtree(tumor_chain)
        elif os.path.isfile(tumor_chain):
            os.remove(tumor_chain)
        cmd_params=[sys.argv[0],'phylovar',
                    '--tree',tree,
                    '--config',config,
                    '--purity',str(args.purity),
                    '--prune',str(args.prune),
                    '--random_seed',str(random_n),
                    '--map',map_dir,
                    '--chain',tumor_chain]
        if args.sex_chr:
            cmd_params.extend(['--sex_chr',args.sex_chr])
        if args.trunk_vars:
            cmd_params.extend(['--trunk_vars',trunk_vars])
        if args.affiliation:
            cmd_params.extend(['--affiliation',affiliation])
        if args.cnvl_dist:
            cmd_params.extend(['--cnvl_dist',cnvl_dist])
        if args.trunk_length:
            cmd_params.extend(['--trunk_length',str(args.trunk_length)])
        logging.info(' Command: %s',' '.join(cmd_params))
        subprocess.run(args=cmd_params,check=True)

#chain2fa
    if args.start<4:
        if os.path.isdir(tumor_fa):
            shutil.rmtree(tumor_fa)
        elif os.path.isfile(tumor_fa):
            os.remove(tumor_fa)

        cmd_params=[sys.argv[0],'chain2fa',
                    '--chain',tumor_chain,
                    '--normal',','.join([os.path.join(normal_fa,'normal.parental_{}.fa'.format(x)) for x in (0,1)]),
                    '--cores',str(args.cores),
                    '--output',tumor_fa]
        logging.info(' Command: %s',' '.join(cmd_params))
        subprocess.run(args=cmd_params,check=True)

#fa2wgs
    random_n=random_int()
    if args.type in ['WGS','BOTH']:
        reads_dir='wgs_reads'
        if os.path.isdir(reads_dir):
            shutil.rmtree(reads_dir)
        elif os.path.isfile(reads_dir):
            os.remove(reads_dir)
        cmd_params=[sys.argv[0],'fa2wgs',
                    '--normal',normal_fa,
                    '--tumor',tumor_fa,
                    '--map',map_dir,
                    '--normal_depth',str(args.normal_depth),
                    '--output',reads_dir,
                    '--random_seed',str(random_n),
                    '--cores',str(args.cores),
                    '--rlen',str(args.rlen),
                    '--art',args.art]
        if args.sectors:
            cmd_params.extend(['--sectors',sectors])
        else:
            cmd_params.extend(['--tumor_depth',str(args.tumor_depth)])
            cmd_params.extend(['--purity',str(args.purity)])
        if args.single:
            cmd_params.extend(['--single'])
        cmd_params_copy=cmd_params[:]
        art_index=cmd_params_copy.index('--art')
        cmd_params_copy[art_index+1]="'{}'".format(cmd_params_copy[art_index+1])
        logging.info(' Command: %s',' '.join(cmd_params_copy))
        subprocess.run(args=cmd_params,check=True)
#fa2wes
    random_n=random_int()
    if args.type in ['WES','BOTH']:
        reads_dir='wes_reads'
        cmd_params=[sys.argv[0],'fa2wes',
                    '--normal',normal_fa,
                    '--tumor',tumor_fa,
                    '--map',map_dir,
                    '--probe',args.probe,
                    '--target',args.target,
                    '--simulator',args.simulator,
                    '--ontarget_ratio',str(args.ontarget_ratio),
                    '--rlen',str(args.rlen),
                    '--purity',str(args.purity),
                    '--output',reads_dir,
                    '--random_seed',str(random_n),
                    '--cores',str(args.cores),
                    '--out_level',str(args.out_level),
                    '--snakemake',args.snakemake]
        if args.sectors:
            cmd_params.extend(['--sectors',sectors])
        if args.tumor_rdepth:
            cmd_params.extend(['--tumor_rdepth',str(args.tumor_rdepth)])
        elif args.tumor_rnum:
            cmd_params.extend(['--tumor_rnum',str(args.tumor_rnum)])
        if args.normal_rdepth:
            cmd_params.extend(['--normal_rdepth',str(args.normal_rdepth)])
        elif args.normal_rnum:
            cmd_params.extend(['--normal_rnum',str(args.normal_rnum)])
        if args.error_model:
            cmd_params.extend(['--error_model',args.error_model])
        if args.separate:
            cmd_params.extend(['--separate'])
        if args.single:
            cmd_params.extend(['--single'])
        cmd_params_copy=cmd_params[:]
        snakemake_index=cmd_params_copy.index('--snakemake')
        snakemake_str = cmd_params_copy[snakemake_index + 1]
        if "'" in snakemake_str:
            snakemake_str = snakemake_str.replace("'",'"')
        cmd_params_copy[snakemake_index + 1] = "'{}'".format(snakemake_str)
        logging.info(' Command: %s',' '.join(cmd_params_copy))
        subprocess.run(args=cmd_params,check=True)

class OutputExistsError(Exception):
    pass
