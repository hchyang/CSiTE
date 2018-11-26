#!/bin/bash

#####################################################
# Author: Bingxin Lu
# Description: This script is used to compare the output of Sequenza (predicted CNVs) against simulated CNVs
# Input: 
#   $1 -- The folder storing output of sequenza (output_alternative_solutions.txt, output_segments.txt); 
#   $2 -- The file containing simulated CNVs; 
#   $3 -- The name of output file 
# Output: 
#   The file specified by $3, which contains a brief summary of CNV precitions; 
#   $3.metrics, which contains metrics obtained by comparing predicted CNVs with simulated CNVs;
#   $3.exome, a TSV file containing simulated CNVs in the exome region; 
#   $3.sequenza.bed, a BED file containing the CNVs predicted by Sequenza; 
#   trunk_cnv.pos, a TSV file containing the position of truncal CNVs
# Assumption: 
#   The following data files are available:
#     input/S03723314_Covered_c3.bed; 
#     input/trunk8000snvs.txt; 
#     input/human_g1k_v37.gnome; 
#     $1/output_alternative_solutions.txt; 
#     $1/output_segments.txt;
#     The file specified by $2; 
#     The script file scripts/compare_cnvs.py
# Command: bash check_cnv.sh $1 $2 $3
#####################################################

# The directory that stores the predicted CNVs
indir=$1
fcnv=$2
fout=$3
# indir=sequenza_output/output/sequenza/sample/
# fcnv="output/phylovar_cnvs/tumor.cnv"
# fout="cnv_stats.txt"

ftarget="input/S03723314_Covered_c3.bed"
ftrunk="input/trunk8000snvs.txt"
genome="input/human_g1k_v37.gnome"

wdir="comparison"   # The directory to store the output of comparison
if [ ! -d $wdir ]; then
  mkdir $wdir 
fi 

fcnv_exome=$wdir/$fout.exome

fcnv_bed=$wdir/tumor_cnv.bed
fcnv_exome_bed=$wdir/tumor_cnv_exome.bed
fsequenza_bed=$wdir/$fout.sequenza.bed

# trunk_cnv.pos, which contains simulated truncal CNVs.   
tail -n+2 $ftrunk | awk '$5 ~ /^+.*/ || $5 ~ /^-.*/' | cut -f1,3,4,5  > $wdir/trunk_cnv.pos
awk 'BEGIN{OFS="\t"}NR>1{if($4 ~ /-/) print $1,$2,$3,"deletion"; else print $1,$2,$3,"amplification"}'  $fcnv | sed 's/^X/999/g' - | sort -k1n -k2n | sed 's/^999/X/g' - > $fcnv_bed
# Extract CNVs in exome region
# $ftarget contains a set of small regions; $fcnv contains a set of large regions; -F Minimum overlap required as a fraction of B. -u:  Write the original A entry once if any overlaps found in B.
bedtools intersect -u -a $fcnv -b $ftarget -F 0.5 > $fcnv_exome
awk 'BEGIN{OFS="\t"}{if($4 ~ /-/) print $1,$2,$3,"deletion"; else print $1,$2,$3,"amplification"}'  $fcnv_exome | sed 's/^X/999/g' - | sort -k1n -k2n | sed 's/^999/X/g' - > $fcnv_exome_bed
bedtools intersect -u -a $wdir/trunk_cnv.pos -b $ftarget -F 0.5 > $wdir/trunk_cnv_exome

fstat="$wdir/$fout"
cat /dev/null > $fstat

# Parse simulations
total=`tail -n+2 $fcnv | wc -l`
ndel=`grep del $fcnv_bed | wc -l`
namp=`grep amp $fcnv_bed | wc -l`
echo "The number of CNVs simulated: $total" >> $fstat
echo "  $ndel deletions" >> $fstat
echo -e "  $namp amplifications\n" >> $fstat
truncal=`tail -n+2 $ftrunk | awk '$5 ~ /^+.*/ || $5 ~ /^-.*/' | wc -l`

echo "The number of truncal CNVs simulated: $truncal" >> $fstat
ndelt=`awk '$5 ~ /^-.*/' $ftrunk | wc -l`
nampt=`awk '$5 ~ /^+.*/' $ftrunk | wc -l`
echo "  $ndelt deletions" >> $fstat
echo -e "  $nampt amplifications\n" >> $fstat

ntruncal=`echo $total - $truncal | bc`
echo "The number of non-truncal CNVs simulated: $ntruncal" >> $fstat
ndeln=`echo $ndel - $ndelt | bc`
nampn=`echo $namp - $nampt | bc`
echo "  $ndeln deletions" >> $fstat
echo -e "  $nampn amplifications\n" >> $fstat

total=`cat $fcnv_exome_bed | wc -l`
ndel=`grep del $fcnv_exome_bed | wc -l`
namp=`grep amp $fcnv_exome_bed | wc -l`
echo "The number of CNVs overlaping with target regions: $total" >> $fstat
echo "  $ndel deletions" >> $fstat
echo -e "  $namp amplifications\n" >> $fstat

truncal=`cat $wdir/trunk_cnv_exome | wc -l`
echo "The number of truncal CNVs overlaping with target regions: $truncal" >> $fstat
ndelt=`awk '$4 ~ /^-.*/' $wdir/trunk_cnv_exome | wc -l`
nampt=`awk '$4 ~ /^+.*/' $wdir/trunk_cnv_exome | wc -l`
echo "  $ndelt deletions" >> $fstat
echo -e "  $nampt amplifications\n" >> $fstat

ntruncal=`echo $total - $truncal | bc`
echo "The number of non-truncal CNVs overlaping with target regions: $ntruncal" >> $fstat
ndeln=`echo $ndel - $ndelt | bc`
nampn=`echo $namp - $nampt | bc`
echo "  $ndeln deletions" >> $fstat
echo -e "  $nampn amplifications\n" >> $fstat

# Parse sequenza output
ploidy=`awk -v OFS='\t' 'NR==2{print $2}' $indir/output_alternative_solutions.txt`
echo -e "Ploidy in sequenza output: $ploidy\n" >> $fstat

purity=`awk -v OFS='\t' 'NR==2{print $1}' $indir/output_alternative_solutions.txt`
echo -e "Purity in sequenza output: $purity\n" >> $fstat

tail -n+2 $indir/output_segments.txt | perl -lane 'if($F[9]>'$ploidy') {print join("\t",@F[0..2], "amplification")} elsif ($F[9]<'$ploidy') {print join("\t",@F[0..2], "deletion")}'  > $fsequenza_bed
sed -i "s/\"//g" $fsequenza_bed

total=`cat $wdir/$fout.sequenza.bed | wc -l`
ndel=`grep del $wdir/$fout.sequenza.bed | wc -l`
namp=`grep amp $wdir/$fout.sequenza.bed | wc -l`
echo "Predicted CNVs by sequenza: $total" >> $fstat >> $fstat
echo "  $ndel deletions" >> $fstat
echo -e "  $namp amplifications\n" >> $fstat

bedtools intersect -u -a $wdir/$fout.sequenza.bed -b $wdir/trunk_cnv.pos -F 0.5 > $wdir/trunk_cnv_sequenza
truncal=`cat $wdir/trunk_cnv_sequenza | wc -l`
ndelt=`grep del $wdir/trunk_cnv_sequenza | wc -l`
nampt=`grep amp $wdir/$fout.sequenza.bed | wc -l`
echo "Predicted truncal CNVs by sequenza: $truncal" >> $fstat
echo "  $ndelt deletions" >> $fstat
echo -e "  $nampt amplifications\n" >> $fstat

ntruncal=`echo $total - $truncal | bc`
ndeln=`echo $ndel - $ndelt | bc`
nampn=`echo $namp - $nampt | bc`
echo "Predicted non-truncal CNVs by sequenza: $ntruncal" >> $fstat
echo "  $ndeln deletions" >> $fstat
echo -e "  $nampn amplifications\n" >> $fstat
echo -e "\n" >> $fstat


# Compared predicted segments with simulated segments overlaping with exome regions
python2 scripts/compare_cnvs.py -e1 $fsequenza_bed -e2 $fcnv_exome_bed -g $genome -e n > $wdir/$fout.metrics


# Remove intermediate files
rm $fcnv_exome_bed
rm $fcnv_bed
rm $wdir/trunk_cnv_exome
rm $wdir/trunk_cnv_sequenza
# intermediate files generated by compare_cnvs.py
rm $wdir/$fout.sequenza_*bed
