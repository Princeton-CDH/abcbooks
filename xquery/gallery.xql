declare namespace util="http://exist-db.org/xquery/util";
declare namespace tei="http://www.tei-c.org/ns/1.0";
<x>
{
let $doc := xs:string(request:get-parameter("doc",()))
for $img in doc(concat('/db/abcbooks/data/transcriptions/',$doc,'.tei.xml'))/tei:TEI/tei:facsimile//tei:graphic
  return <url>{$img/@url}</url>
}</x>
(:
let $xslt := doc('/db/abcbooks/transform/gallery.xsl')
return transform:transform($facs, $xslt ,())
:)


