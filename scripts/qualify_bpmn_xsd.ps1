param([Parameter(Mandatory=$true)][string]$SiteRoot,[Parameter(Mandatory=$true)][string]$SchemaPath)
$ErrorActionPreference='Stop'
$taskSchemas=[System.Xml.Schema.XmlSchemaSet]::new()
$taskSchemas.XmlResolver=[System.Xml.XmlUrlResolver]::new()
[void]$taskSchemas.Add('http://www.omg.org/spec/BPMN/20100524/MODEL',(Resolve-Path -LiteralPath $SchemaPath).Path)
$taskSchemas.Compile()
$taskSettings=[System.Xml.XmlReaderSettings]::new()
$taskSettings.ValidationType=[System.Xml.ValidationType]::Schema
$taskSettings.Schemas=$taskSchemas
$taskSettings.add_ValidationEventHandler({param($sender,$eventArgs) throw $eventArgs.Message})
$taskFiles=@(Get-ChildItem -LiteralPath $SiteRoot -Recurse -File -Filter '*.bpmn')
foreach($taskFile in $taskFiles){
 $taskReader=[System.Xml.XmlReader]::Create($taskFile.FullName,$taskSettings)
 try{while($taskReader.Read()){} }finally{$taskReader.Dispose()}
}
@{status='PASS_SCOPED';scope='BPMN_2_0_2_XML_STRUCTURE_NOT_EXECUTION_EQUIVALENCE';exports=$taskFiles.Count}|ConvertTo-Json -Compress
