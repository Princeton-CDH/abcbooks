declare namespace util="http://exist-db.org/xquery/util";
declare namespace tei="http://www.tei-c.org/ns/1.0";
declare option exist:serialize "method=json media-type=text/javascript"; 
<covers>
{
for $doc in collection('/db/abcbooks/data/transcriptions')

return <book>
{$doc//tei:sourceDesc/tei:bibl/tei:title}
<id>{xs:string($doc//tei:publicationStmt/tei:idno[@type='abcbooksid'])}</id>
</book>
}</covers>