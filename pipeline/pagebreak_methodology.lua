-- Keep the symbol-migration table and version history together in the PDF.
function Header(element)
  if element.level == 2 then
    local text = pandoc.utils.stringify(element.content)
    if string.match(text, "^7%.") then
      return {pandoc.RawBlock("latex", "\\clearpage"), element}
    end
  end
end
