#!/usr/bin/perl

#Read an input file from "show ip bgp vpnv4 all", fill in the blanks, make unique and sort.
#Usage: input output next-hop

open INF, @ARGV[0] or die "syntax: bgp.pl input.txt output.txt";
open FILECOUNT, @ARGV[0];
chomp(my $destination = $ARGV[1]);
open OUTPUT, ">$destination" or die "Problem with destination file $!";
print OUTPUT "RD\tPrefix\tNext Hop\n";
$filternh = $ARGV[2];
if (!$filternh) { $filternh = ".*"; }
my @outputvar;

while (<FILECOUNT>) {};
$linecount = $.;
$linenum = 0;
close FILECOUNT;
print "$linecount lines found in the file\n";

while (<INF>) {
	$linenum++;
        $percentage = int(($linenum / $linecount) * 100);
	print "\r$percentage% complete";
	$line=$_;
	chomp ($line);
	$line =~ s/\r//g;
	if ($line =~ /Route Distinguisher: (.*)/) { $rd=$1; chomp($rd); }
	if ($line !~ /router ID|Route|bgp/) {
	if ($line =~ /^s|^d|^h|^\*|^\>|^i|^r|[0-9]{1,3}\.[0-9]{1,3}/g) {
		$linewithoutheader = substr($line, 3);

		if ($linewithoutheader =~ /^([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})/) { $prefix = $1; }
		if ($linewithoutheader =~ /^([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\/[0-9]{1,2})/) { $prefix = $1; }		
		$linewithoutprefix = substr($linewithoutheader, 17);
                if ( substr($linewithoutprefix, 3, 3) =~ /[0-9]|\./ ) {
			$tabline = $linewithoutprefix;
			$tabline =~ s/( )+/\t/ig;
			@tabroute = split (/\t/,$tabline);
			if ( $tabroute[0] =~ /$filternh$/ ) {
				$calcvar = qq($rd\t$prefix\t$tabroute[0]\t$tabroute[1]\t$tabroute[2]\n);
				push (@outputvar, $calcvar);
			}
		}
			
	}
	}
	undef @route;
	undef @tabroute;
	undef $calcvar;
}
my %uniqscalar;
my @unique = grep { ! $uniqscalar{$_}++ } @outputvar;
@sortroutes = sort @unique;
$countroutes = @sortroutes;
print "\n$countroutes routes processed!\n";
print OUTPUT @sortroutes;


