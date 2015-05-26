<xsl:stylesheet xmlns="http://www.w3.org/1999/xhtml" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:tei="http://www.tei-c.org/ns/1.0" version="1.0">
    <xsl:output method="html" doctype-system="http://www.w3.org/TR/html4/strict.dtd" doctype-public="-//W3C//DTD HTML 4.01//EN" indent="yes"/>
    <xsl:template match="/">
        <div id="book-header">
            <xsl:apply-templates/>
        </div>
    </xsl:template>
    <xsl:template match="//tei:title">
        <xsl:value-of select="."/>
    </xsl:template>
    <xsl:template match="//tei:publicationStmt/tei:idno">
        Voyager ID: <xsl:value-of select="."/>
    </xsl:template>
    <xsl:template match="//tei:ab">
        <xsl:for-each select="//tei:lb">
            <div>
                <xsl:value-of select="normalize-space(./following::node())"/>
            </div>
        </xsl:for-each>
    </xsl:template>
</xsl:stylesheet>