"""Verify a signed XPI in a disposable release-Firefox profile, never the user's profile."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time
import zipfile

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

parser=argparse.ArgumentParser()
parser.add_argument('--xpi',type=Path,required=True)
parser.add_argument('--unsigned',type=Path,required=True)
parser.add_argument('--firefox',type=Path,required=True)
parser.add_argument('--geckodriver',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
xpi=args.xpi.resolve();unsigned=args.unsigned.resolve()
with zipfile.ZipFile(xpi) as signed,zipfile.ZipFile(unsigned) as original:
    names=[entry.filename for entry in signed.infolist()]
    assert len(names)==len(set(names)),'Duplicate ZIP entries'
    assert all(not entry.is_absolute() and '..' not in entry.parts for entry in map(Path,names)),'Unsafe ZIP path'
    assert sum(entry.file_size for entry in signed.infolist())<16*1024*1024,'Unexpected XPI size'
    reference={entry.filename for entry in original.infolist() if not entry.is_dir()}
    actual={entry.filename for entry in signed.infolist() if not entry.is_dir()}
    assert not reference-actual,'Missing uploaded files'
    assert actual-reference=={'META-INF/cose.manifest','META-INF/cose.sig','META-INF/manifest.mf','META-INF/mozilla.sf','META-INF/mozilla.rsa'},'Unexpected added files'
    manifest=json.loads(signed.read('manifest.json'))
    assert manifest==json.loads(original.read('manifest.json')),'Manifest content changed'
    assert manifest['version']=='0.1.16' and manifest['browser_specific_settings']['gecko']['id']=='vault@kryptocorelabs'
    for name in reference-{'manifest.json'}:
        assert signed.read(name)==original.read(name),'Changed payload: '+name

def state(driver):
    with driver.context('chrome'):
        return driver.execute_async_script('''
          const done=arguments[arguments.length-1];
          const {AddonManager}=ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
          AddonManager.getAddonByID('vault@kryptocorelabs').then(addon => done({
            signaturesRequired: Services.prefs.getBoolPref('xpinstall.signatures.required', true),
            signedConstant: AddonManager.SIGNEDSTATE_SIGNED,
            addon: addon ? {id:addon.id,version:addon.version,isActive:addon.isActive,
              appDisabled:addon.appDisabled,userDisabled:addon.userDisabled,
              signedState:addon.signedState,temporarilyInstalled:addon.temporarilyInstalled} : null
          }), error=>done({error:String(error)}));
        ''')

with tempfile.TemporaryDirectory(prefix='firefox-signing-',dir=args.output) as temp:
    root=Path(temp);profile=root/'profile';profile.mkdir()
    tampered=root/'tampered.xpi'
    with zipfile.ZipFile(xpi) as original,zipfile.ZipFile(tampered,'w',zipfile.ZIP_DEFLATED) as output:
        for entry in original.infolist():
            data=original.read(entry)
            if entry.filename=='popup.css':data+=b'\n/* synthetic signature-negative test */\n'
            output.writestr(entry.filename,data)
    report={'version':'0.1.16','addon_id':'vault@kryptocorelabs',
            'sha256':hashlib.sha256(xpi.read_bytes()).hexdigest(),
            'payload_matches_submission':True,'manifest_semantically_identical':True,
            'signature_required':True,'negative_checks':[],'states':[]}
    for phase in ('install','restart'):
        options=Options();options.binary_location=str(args.firefox.resolve())
        options.add_argument('-headless');options.add_argument('-profile');options.add_argument(str(profile))
        options.set_preference('xpinstall.signatures.required',True)
        options.set_preference('extensions.update.enabled',False)
        options.set_preference('browser.shell.checkDefaultBrowser',False)
        service=Service(str(args.geckodriver.resolve()),service_args=['--allow-system-access'],
                        log_output=str(args.output/f'geckodriver-{phase}.log'))
        with webdriver.Firefox(options=options,service=service) as driver:
            assert Path(driver.capabilities['moz:profile']).resolve()==profile.resolve(),'Profile was cloned instead of reused'
            report['firefox_version']=driver.capabilities['browserVersion']
            if phase=='install':
                for label,archive in (('unsigned',unsigned),('tampered',tampered)):
                    try:driver.install_addon(str(archive),temporary=False)
                    except WebDriverException:
                        assert state(driver)['addon'] is None,'Rejected package left an installed add-on'
                        report['negative_checks'].append({'case':label,'rejected':True})
                    else:raise AssertionError(label+' package was accepted with signature enforcement')
                assert driver.install_addon(str(xpi),temporary=False)=='vault@kryptocorelabs'
            end=time.monotonic()+15
            while True:
                current=state(driver)
                if (current.get('addon') or {}).get('isActive') or time.monotonic()>=end:break
                time.sleep(.1)
            addon=current['addon']
            assert current['signaturesRequired'] and addon,'Missing add-on or signature enforcement'
            assert addon['version']=='0.1.16' and addon['signedState']==current['signedConstant'],'Firefox did not confirm ordinary Mozilla signing'
            assert addon['isActive'] and not addon['appDisabled'] and not addon['userDisabled'] and not addon['temporarilyInstalled'],'Add-on is not persistently active'
            report['states'].append({'phase':phase,**current})
            print('PASS',phase,': release Firefox accepted the signed XPI with signatures required; active and non-temporary.')
    report['restart_persistence_verified']=True
    (args.output/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('Signed-XPI verification passed, including unsigned/tampered rejection and restart persistence.')
