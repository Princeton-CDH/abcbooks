<xsl:stylesheet xmlns="http://www.w3.org/1999/xhtml" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:tei="http://www.tei-c.org/ns/1.0" version="1.0">
    <xsl:output method="html" doctype-system="http://www.w3.org/TR/html4/strict.dtd" doctype-public="-//W3C//DTD HTML 4.01//EN" indent="yes"/>
    
    <xsl:template match="/">
        <div id="book-header">
            <xsl:apply-templates/>
        </div>
    </xsl:template>

    <xsl:template match="tei:teiHeader/tei:fileDesc">
        <xsl:variable name="bookid"><xsl:value-of select="tei:publicationStmt/tei:idno[@type='abcbooksid']"/></xsl:variable>
        <div id="description">
            <div id="cover">
                <img><xsl:attribute name="src">/images/<xsl:value-of select="$bookid"/>/cover.png</xsl:attribute></img></div>
            <div id="meta">
        <h2>
            <xsl:value-of select="tei:titleStmt/tei:title"/>
        </h2>
        <div id="publication_stmt">
            <p><xsl:value-of select="tei:publicationStmt/tei:publisher"/></p>
            <p><xsl:value-of select="tei:publicationStmt/tei:pubPlace"/></p>
            <p><xsl:value-of select="tei:publicationStmt/tei:idno[@type='voyagerid']"/></p>
            <p><xsl:value-of select="tei:publicationStmt/tei:idno[@type='abcbooksid']"/></p>
        </div>
        <div id="source">
            <p><b><xsl:value-of select="tei:sourceDesc/tei:bibl/tei:title"/></b></p>
            <p><b><xsl:copy-of select="tei:sourceDesc/tei:bibl"/></b></p>
        </div>
            </div>
        </div>
    </xsl:template>

    <xsl:template match="tei:facsimile">
        <div id="gallery">
            <xsl:apply-templates/>
        </div>
    </xsl:template>
    
    <xsl:template match="tei:surface">
        <div id="page_image"><img><xsl:attribute name="src"><xsl:value-of select="tei:graphic/@url"/></xsl:attribute></img></div>
    </xsl:template>
    
    
    
    <xsl:template match="//tei:text/tei:body"/>
    <xsl:template match="//tei:text/tei:back"/>

    <xsl:template match="//tei:ab">
        <xsl:for-each select="//tei:lb">
            <div>
                <xsl:value-of select="normalize-space(./following::node())"/>
            </div>
        </xsl:for-each>
    </xsl:template>
</xsl:stylesheet>