xquery version "1.0";
declare namespace util="http://exist-db.org/xquery/util";
declare namespace tei="http://www.tei-c.org/ns/1.0";
(:declare namespace output = "http://www.w3.org/2010/xslt-xquery-serialization";:)
(:declare namespace json="http://www.json.org";:)

(: Switch to JSON serialization
declare option output:method "json";
declare option output:media-type "text/javascript";
 :)

let $doc := xs:string(request:get-parameter("doc",()))
let $doco := doc(concat('/db/abcbooks/data/transcriptions/',$doc,'.tei.xml'))

return $doco

