declare namespace util="http://exist-db.org/xquery/util";
declare namespace tei="http://www.tei-c.org/ns/1.0";

declare function local:milestone-chunk(
  $ms1 as element(),
  $ms2 as element(),
  $node as node()*
) as node()*
{
  typeswitch ($node)
    case element() return
      if ($node is $ms1) then $node
      else if ( some $n in $node/descendant::* satisfies ($n is $ms1 or $n is $ms2) )
      then
        element { name($node) }
                { for $i in ( $node/node() | $node/@* )
                  return local:milestone-chunk($ms1, $ms2, $i) }
      else if ( $node >> $ms1 and $node << $ms2 ) then $node
      else ()
    case attribute() return $node (: will never match attributes outside non-returned elements :)
    default return 
      if ( $node >> $ms1 and $node << $ms2 ) then $node
      else ()
};


let $doc := xs:string(request:get-parameter("doc",()))
let $pagefrom := request:get-parameter("page",())

let $pageto := xs:integer($pagefrom) + 1
let $idfrom := concat("page_image",$pagefrom)
let $idto := concat("page_image",$pageto)
let $input := doc(concat('/db/abcbooks/data/transcriptions/',$doc,'.tei.xml'))/tei:TEI/tei:text

let $result := local:milestone-chunk($input//tei:pb[@facs=$idfrom], $input//tei:pb[@facs=$idto], $input)
let $xslt := doc('/db/abcbooks/transform/page.xsl')
(:
return transform:transform($result, $xslt ,())

:)
return $result

