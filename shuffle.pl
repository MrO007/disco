#!/usr/bin/perl
open INF, $ARGV[0] or die "syntax: bgp.pl input.txt output.txt";
chomp ($ARGV[1]);
$findstring = $ARGV[1];
while (<INF>) {
	$line = $_;
	chomp ($line);
	$line =~ s/\r//g;
	$line =~ s/^\s+//;
	$line =~ s/\s+$//;
	if ( $line =~ m/$findstring/ ) {
		print "$AP\n";
		undef $AP;
		$AP = $line;
	} else {
	$AP .= "," . $line;
	}

}
print "$AP\n";
