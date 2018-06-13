 map(if . == null then null else {
   id: .id,
   name: (.name // ""),
   shortName: ((.name // "") | [ splits("\\s+") ] | if length > 1 then "\(.[0]) \(.[-1])" else join(" ") end),
   advisors: [ (.degrees // []) | .[].advisors[][1] ],
   description: ([ (.degrees // []) | .[] | "\(.university) (\(.years))"] | join(", ")),
   countries: ([ (.degrees // []) | .[] | .country[] ] | join(", ")),
   score: .score,
   wikiLink: .wiki_link
} end)

