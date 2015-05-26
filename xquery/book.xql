declare namespace util="http://exist-db.org/xquery/util";
declare namespace tei="http://www.tei-c.org/ns/1.0";

let $doc := xs:string(request:get-parameter("doc",()))
let $header := doc(concat('/db/abcbooks/data/transcriptions/',$doc,'.tei.xml'))/tei:TEI/tei:teiHeader
let $xslt := doc('/db/abcbooks/transform/book.xsl')

return transform:transform($header, $xslt ,())
(:return $header:)


