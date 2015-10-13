<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
	xmlns:xs="http://www.w3.org/2001/XMLSchema"
	xmlns:xd="http://www.oxygenxml.com/ns/doc/xsl"
	xmlns:tei="http://www.tei-c.org/ns/1.0"
	xmlns:mods="http://www.loc.gov/mods/v3"
	xmlns:xlink="http://www.w3.org/1999/xlink"
	xmlns:local="http://library.princeton.edu/cew" 
	exclude-result-prefixes="xs xd mods local"
	version="2.0">
	<xd:doc scope="stylesheet">
		<xd:desc>
			<xd:p><xd:b>Created on:</xd:b> Oct 13, 2015</xd:p>
			<xd:p><xd:b>Author:</xd:b> cwulfman</xd:p>
			<xd:p></xd:p>
		</xd:desc>
	</xd:doc>
	
	<xsl:output method="xml" indent="yes" encoding="UTF-8" />
	
	<xsl:variable name="svc">
		<xsl:text>http://diglib.princeton.edu/tools/v2m/</xsl:text>
	</xsl:variable>

	<xsl:template match="book">
		<xsl:variable name="mods" select="document(concat($svc, @voyagerid))" />
		<xsl:variable name="filepath">
			<xsl:value-of select="concat('/tmp/pudl0111/', @voyagerid, '.tei.xml')" />
		</xsl:variable>
			
		<xsl:result-document method="xml" href="{$filepath}">
		<TEI xmlns="http://www.tei-c.org/ns/1.0">
			<teiHeader>
				<fileDesc>
					<titleStmt>
						<title></title>
					</titleStmt>
					<publicationStmt>
						<publisher>Princeton University</publisher>
						<pubPlace>Princeton, New Jersey</pubPlace>
						<idno type='voyagerid'><xsl:value-of select="@voyagerid" /></idno>
					</publicationStmt>
				</fileDesc>
				<sourceDesc>
					<xsl:apply-templates select="$mods"></xsl:apply-templates>
				</sourceDesc>
			</teiHeader>
			<facsimile>
				<xsl:for-each select="page">
					<surface>
						<xsl:attribute name="xml:id">
							<xsl:value-of select="concat('page_image', position())"/>
						</xsl:attribute>							
						<graphic ana="lowres" mimeType="image/jp2" url="{@name}" />
					</surface>
				</xsl:for-each>
			</facsimile>
			<text>
				<body>
					<xsl:for-each select="page">
						<pb facs="{ concat('page_image', position()) }" n="{ position() }"/>
					</xsl:for-each>
				</body>
			</text>
		</TEI>
		</xsl:result-document>
	</xsl:template>
	
	
	
	
	<!-- MODS templates -->
	<xsl:template match="mods:mods">
		<biblStruct>
			<monogr>
				<title level="m">
					<xsl:apply-templates select="mods:titleInfo[1]"/>
				</title>
				<imprint>
					<pubPlace>
						<xsl:value-of select="mods:originInfo/mods:place/mods:placeTerm[@type='text']" />
					</pubPlace>
					<publisher>
						<xsl:value-of select="mods:originInfo/mods:publisher" />
					</publisher>
					<date>
						<xsl:value-of select="mods:originInfo/mods:dateIssued" />
					</date>
				</imprint>
			</monogr>
		</biblStruct>
	</xsl:template>
	
	<xsl:template match="mods:relatedItem[@type='host']">
		<relatedItem type="host" target="{@xlink:href}"/>
	</xsl:template>
	
	<xsl:template match="mods:relatedItem[@type='constituent']">
		<relatedItem type="constituent">
			<xsl:if test="@ID">
				<xsl:attribute name="xml:id" select="@ID"/>
			</xsl:if>
			<biblStruct>
				<analytic>
					<title level="a">
						<xsl:apply-templates select="mods:titleInfo"/>
					</title>
					<xsl:apply-templates select="mods:name"/>
					<xsl:apply-templates select="mods:language"/>
				</analytic>
				<monogr>
					<imprint>
						<classCode scheme="CCS">
							<xsl:value-of select="mods:genre[@type='CCS']"/>
						</classCode>
						<xsl:apply-templates select="mods:part/mods:extent"/>
						<!--<biblScope type="pp" corresp="{mods:part/mods:extent[@unit='page']/mods:start}"/>-->
					</imprint>
				</monogr>
				<xsl:apply-templates select="mods:note"/>
				<xsl:apply-templates select="mods:relatedItem[@type='constituent']"/>
			</biblStruct>
		</relatedItem>
	</xsl:template>
	
	<xsl:template
		match="mods:relatedItem[@type='constituent']/mods:part/mods:extent[@unit='page' and mods:list]">
		<xsl:variable name="pnums" select="tokenize(mods:list, '-')"/>
		<biblScope unit="page" from="{$pnums[1]}" to="{$pnums[2]}">
			<xsl:value-of select="mods:list"/>
		</biblScope>
	</xsl:template>
	
	<xsl:template
		match="mods:relatedItem[@type='constituent']/mods:part/mods:extent[@unit='page' and mods:start]">
		<biblScope unit="page">
			<xsl:value-of select="mods:start"/>
		</biblScope>
	</xsl:template>
	
	<xsl:template match="mods:titleInfo">
		
		<xsl:if test="mods:nonSort">
			<seg type="nonSort">
				<xsl:apply-templates select="mods:nonSort"/>
			</seg>
		</xsl:if>
		<seg type="main">
			<xsl:apply-templates select="mods:title"/>
		</seg>
		<xsl:if test="mods:subTitle">
			<seg type="sub">
				<xsl:apply-templates select="mods:subTitle"/>
			</seg>
		</xsl:if>
		
	</xsl:template>
	
	<xsl:template match="mods:name">
		<respStmt>
			<persName>
				<xsl:if test="@valueURI">
					<xsl:attribute name="ref">
						<xsl:value-of select="@valueURI" />
					</xsl:attribute>
				</xsl:if>
				<xsl:value-of select="mods:displayForm"/>
			</persName>
			<resp>
				<xsl:value-of select="mods:role/mods:roleTerm"/>
			</resp>
		</respStmt>
	</xsl:template>
	
	<xsl:template match="mods:language">
		<textLang mainLang="{mods:languageTerm}"/>
	</xsl:template>
	
	
</xsl:stylesheet>