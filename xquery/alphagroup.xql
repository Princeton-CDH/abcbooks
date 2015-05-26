declare namespace util="http://exist-db.org/xquery/util";
declare namespace tei="http://www.tei-c.org/ns/1.0";

<searchresult>
    {
let $q := xs:string(request:get-parameter("q",()))
(:
let $q := 'A'
:)
let $db := collection('/db/abcbooks/data/transcriptions')
let $pagexslt := doc('/db/abcbooks/transform/page_transcript.xsl')


for $r in $db//tei:div[@ana=$q]
  let $result := 
    <result>
    {$r/ancestor::tei:text/preceding-sibling::tei:teiHeader//tei:idno[@type="abcbooksid"]}
	<filename>{xs:string($r/ancestor::tei:text/preceding-sibling::tei:facsimile/tei:surface[@xml:id=xs:string($r/preceding-sibling::tei:pb[1]/@facs)]/tei:graphic/@url)}</filename>
    {$r/ancestor::tei:text/preceding-sibling::tei:teiHeader//tei:sourceDesc/tei:bibl/tei:title}
    <html>
	{transform:transform($r/*, $pagexslt ,())}
    </html>
    </result>

return $result

(:
let $xslt := doc('/db/abcbooks/transform/search.xsl')
return transform:transform($result, $xslt ,())
:)
}   
</searchresult>


