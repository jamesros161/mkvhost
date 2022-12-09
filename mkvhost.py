#!/usr/bin/python3
import os
import sys
import argparse
import random
import string
import json
from subprocess import Popen, PIPE

PARSER = argparse.ArgumentParser()
DOMAIN = 'boldgrid.dev'
SITE_AVAIL_DIR = '/etc/apache2/sites-available/'
VHOST_CONF_DIR = '/var/www/vhost_confs'
APACHE_BASE_DIR = '/var/www/html/'
APACHE_LOG_DIR = '/var/log/apache2/'
MYSQL_USER = 'phpmyadmin'
MYSQL_PASS = {{MYSQL PASSWORD}}
ADMIN_EMAIL = 'wordpress@boldgrid.dev'

# default statement to create database and database user
# a=db_name, b=db_user, c=db_pass
MYSQL_STATEMENT = (
    "CREATE DATABASE {a};"
    "GRANT ALL ON {a}.* TO '{b}'@'localhost' IDENTIFIED BY '{c}';"
    "FLUSH PRIVILEGES;"
)

# default vhost temlate string
# a=fqdn , b=APACHE_BASE_DIR, c=site, d=APACHE_LOG_DIR
DEFAULT_VHOST = (
    """<VirtualHost *:80>
        ServerName {a}
        DocumentRoot {b}{c}

        ErrorLog {b}{c}/error.log
        CustomLog {d}{c}.access.log combined

        <Directory {b}{c}/>
            Options FollowSymLinks
            AllowOverride All
            Require all granted
        </Directory>
    </VirtualHost>
	<IfModule mod_ssl.c>
		SSLStaplingCache shmcb:/var/run/apache2/stapling_cache(128000)
		<VirtualHost *:443>
				ServerName {a}
				DocumentRoot {b}{c}

				ErrorLog {b}{c}/ssl.error.log
				CustomLog {d}{c}-ssl.access.log combined

				<Directory {b}{c}/>
					Options FollowSymLinks
					AllowOverride All
					Require all granted
				</Directory>

			SSLCertificateFile /etc/letsencrypt/live/boldgrid.dev/fullchain.pem
			SSLCertificateKeyFile /etc/letsencrypt/live/boldgrid.dev/privkey.pem

			Include /etc/letsencrypt/options-ssl-apache.conf

			Header always set Strict-Transport-Security "max-age=31536000"

			SSLUseStapling on

		</VirtualHost>
	</IfModule>"""
    )

# default htaccess template string
# a=doc_root
DEFAULT_HTACCESS = (
	"""php_value error_log "{a}/php.error.log"

	<IfModule mod_rewrite.c>
	RewriteEngine On
	RewriteRule .* - [E=HTTP_AUTHORIZATION:%{{HTTP:Authorization}}]
	RewriteBase /
	RewriteRule ^index\.php$ - [L]
	RewriteCond %{{REQUEST_FILENAME}} !-f
	RewriteCond %{{REQUEST_FILENAME}} !-d
	RewriteRule . /index.php [L]
	</IfModule>"""
)

def get_arguments():
	PARSER.add_argument(
		'site',
		help='subdomain of ' + '.' + DOMAIN
		)
	PARSER.add_argument(
		'-w', '--wordpress',
		help='This is a WordPress Site',
		action="store_true"
	)
	PARSER.add_argument(
		'-I', '--inspirations',
		help='Install BoldGrid Inspirations',
		action="store_true"
	)
	PARSER.add_argument(
		'-p','--plugins', nargs='+', help='<optional> Plugins to install'
	)
	PARSER.add_argument(
		'-g','--git', nargs="+", help="<optional> Git Repos to clone to wp-content/plugins"
	)
	PARSER.add_argument(
		'-s','--sprout', help='<optional> Sprout Version to install'
	)
	PARSER.add_argument(
		'-b','--branch', help='<optional> Sprout Version to install'
	)
# Use like:
	return PARSER.parse_args()

def set_params( args ):
	site = ''
	fqdn = ''
	plugins = ''
	is_site_wp = False
	git_repos = False
	sprout_version = False
	sprout_branch = False
	if args.site:
		if args.site.isalnum():
			site = args.site
			fqdn = args.site + '.' + DOMAIN
		else:
			sys.exit('Site names must contian only alphanumeric characters')
	else:
		sys.exit(1)
	if args.wordpress:
		is_site_wp = True
	if args.plugins:
		plugins = args.plugins
	if args.git:
		git_repos = args.git
	if args.sprout:
		sprout_version = args.sprout
	if args.branch:
		sprout_branch  = args.branch
	return ( args, site, fqdn, is_site_wp, plugins, git_repos, sprout_version, sprout_branch )

def randomStringDigits(stringLength=12):
	"""Generate a random string of letters and digits """
	lettersAndDigits = string.ascii_letters + string.digits
	return ''.join(random.choice(lettersAndDigits) for i in range(stringLength))

def create_vhost( fqdn, site ):
	vhost_conf_string = DEFAULT_VHOST.format( a=fqdn , b=APACHE_BASE_DIR, c=site, d=APACHE_LOG_DIR )
	vhost_file_name = fqdn + '.conf'
	vhost_file_path = SITE_AVAIL_DIR + vhost_file_name
	put_contents_in( vhost_file_path, vhost_conf_string )

def mk_doc_root( site ):
	doc_root = APACHE_BASE_DIR + site
	mkdir_args = [
		'mkdir',
		'-p',
		doc_root
	]
	htaccess_file_path = doc_root + '/.htaccess'
	htaccess_contents = DEFAULT_HTACCESS.format( a=doc_root )
	run_cmd( mkdir_args )
	put_contents_in( htaccess_file_path, htaccess_contents )

def create_db_user( site ):
	db_name = site + '_wp'
	db_user = site + '_wp'
	db_pass = randomStringDigits()
	mysql_args = [
		'mysql',
		'-p' + MYSQL_PASS,
		'-u', MYSQL_USER,
		'-e', MYSQL_STATEMENT.format( a=db_name, b=db_user, c=db_pass, d=MYSQL_PASS, e=MYSQL_USER )
	]
	run_cmd( mysql_args )
	return {
		'db_name': db_name,
		'db_user': db_user,
		'db_pass': db_pass
	}

def enable_site( fqdn ):
	response = [ run_cmd( ['a2ensite', fqdn ] ) ]
	response.append( run_cmd( ['systemctl', 'restart', 'apache2'] ) )
	return response

def run_cmd( cmd_args, cwd=False ):
	if cwd:
		response, error = Popen(cmd_args, stderr=PIPE, stdout=PIPE, cwd=cwd).communicate()
	else:
		response, error = Popen(cmd_args, stderr=PIPE, stdout=PIPE).communicate()
	try:
		response = response.decode()
	except (UnicodeDecodeError, AttributeError):
		pass

	try:
		error = error.decode()
	except (UnicodeDecodeError, AttributeError):
		pass

	return [ response, error ]

def put_contents_in( path, contents ):
	with open( path, 'w+' ) as f:
		f.write( contents )

def set_ssl( fqdn ):
	set_ssl_args = [
		'certbot',
		'--apache',
		'--agree-tos',
		'--redirect',
		'--hsts',
		'--staple-ocsp',
		'--must-staple',
		'-d', fqdn,
		'--email', ADMIN_EMAIL
		]
	return run_cmd( set_ssl_args )

def install_wordpress( site, fqdn ):
	path = APACHE_BASE_DIR + site
	print( '\nPATH: ' + path + '\n')
	print( '\nwp_core_download: ' + wp_core_download( path )[0] )
	db_data = wp_config_create( site, path )
	installation = wp_core_install( site, path, fqdn )
	return { 'admin_pass': installation, 'db_data': db_data }

def wp_core_download( path ):
	core_download_response = run_cmd([
		'wp', 'core', 'download',
		'--force', '--path=' + path,
		'--allow-root'
		])
	return core_download_response

def wp_config_create( site, path ):
	db_data = create_db_user( site )
	wp_config = run_cmd([
		'wp', 'config', 'create',
		'--dbname=' + db_data['db_name'],
		'--dbuser=' + db_data['db_user'],
		'--dbpass=' + db_data['db_pass'],
		'--path=' + path,
		'--allow-root'
	])

	wp_debug = run_cmd([
		'wp', 'config', 'set',
		'WP_DEBUG',
		'true',
		'--path=' + path,
		'--allow-root'
	])

	print('\nWP_DEBUG: \n'.join(map(str, wp_debug)))

	return db_data

def wp_core_install( site, path, fqdn ):
	admin_pass = randomStringDigits()
	core_inst_response = run_cmd([
		'wp', 'core', 'install',
		'--url=https://' + fqdn,
		'--title=BG Dev - ' + site.capitalize(),
		'--admin_user=' + site + 'adm',
		'--admin_password=' + admin_pass,
		'--admin_email=' + ADMIN_EMAIL,
		'--skip-email', '--path=' + path,
		'--allow-root'
	])
	print( '\nwp_core_install: ' + core_inst_response[0] )

	return admin_pass

def install_plugins( plugins, site ):
	print( '\nInstalling Plugins:\n\n')
	path = APACHE_BASE_DIR + site
	for plugin in plugins:
		print( '\n\t' + str( install_plugin( plugin, path ) ) )
		print( '\n\t' + str( activate_plugin( plugin, path ) ) )

def install_plugin( plugin, path ):
	return run_cmd([
		'wp', 'plugin', 'install', plugin,
		'--path=' + path, '--allow-root'
	])

def activate_plugin( plugin, path ):
	return run_cmd([
		'wp', 'plugin', 'activate', plugin,
		'--path=' + path, '--allow-root'
	])

def fix_perms( site ):
	path = APACHE_BASE_DIR + site
	run_cmd( [
		'chown', '-R', 'www-data:www-data', path
	])
	run_cmd( [
		'chown', '-R', 'www-data:www-data', VHOST_CONF_DIR
	])

def write_vhost_conf( site, installation_data, clone_git_results):
	path = VHOST_CONF_DIR + '/' + site + '.conf'
	conf = {
		'ADMIN_URL': 'https://' + site + '.' + DOMAIN + '/wp-admin/',
		'ADMIN_USER': site + 'adm',
		'ADMIN_PASS': installation_data['admin_pass'],
		'DB_DATA': installation_data['db_data'],
		'GITS_CLONED': clone_git_results
	}
	pretty_json =  json.dumps( conf, sort_keys=False, indent=4, separators=(',', ': '))
	with open(path, 'w+') as fs:
		fs.write(pretty_json)

def clone_gits( git_repos, site ):
	print( '\nCloning Git Repo(s): ' + ', '.join(git_repos) + '\n' )
	clone_results = {
		'successful': [],
		'failed': []
	}

	for git in git_repos:
		repo_name = ''
		repo_url = ''
		split_git = git.split('/')
		if len(split_git) == 2:
			repo_name = str(split_git[0]) + '/' + split_git[1]
			repo_url = 'https://github.com/' + str(split_git[0]) + '/' + split_git[1] + '.git'
		elif len(split_git) == 1:
			repo_name = 'boldgrid/' + split_git[0]
			repo_url = 'https://github.com/boldgrid/' + split_git[0] + '.git'
		elif len(split_git) > 2:
			clone_results['failed'].append(
					[git, 'Invalid git repo format. Unable to clone repo']
					)
			repo_url = ''
		else:
			repo_url = 'https://github.com/' + repo_name + '.git'

		if repo_url:
			path = APACHE_BASE_DIR + site + '/wp-content/'
			git_cmd = ['git', '-C', path, 'clone', repo_url]
			_, error = run_cmd( git_cmd )
			error_split = error.splitlines()
			if error and 'No such file or directory' in error:
				clone_results['failed'].append('No git repos have been cloned since this site does not have WordPress installed yet!' )
				break
			elif len(error_split) == 1 and error_split[0] == "Cloning into '" + split_git[-1] + "'...":
				clone_results['successful'].append(repo_name)
				if 'boldgrid' in split_git[-1]:
					deps = install_dev_deps( path + '/' + split_git[-1] )
					clone_results['successful'].append([repo_name, deps])
				else:
					clone_results['successful'].append(repo_name)
			else:
				clone_results['failed'].append(
					[repo_name, error_split]
					)
	return clone_results

def install_dev_deps( path ):
	yarn_args = ['yarn', 'install']
	yarn_r, yarn_e = run_cmd(yarn_args, path)

	composer_args = ['composer', '-o', 'install']
	composer_r, composer_e = run_cmd(composer_args, path)

	return {
		'yarn': [ yarn_r, yarn_e ],
		'composer': [ composer_r, composer_e ]
	}

def install_sprout( sprout_version, sprout_branch, site ):
	print( '\nInstalling Sprout: ' + sprout_version + '\n' )
	print( '\nInstalling Branch: ' + sprout_branch + '\n' )

	response = clone_gits( ['sprout-invoices' ], site )
	print( response )

	path = APACHE_BASE_DIR + site + '/wp-content/sprout-invoices'
	git_cmd = ['git', '-C', path, 'checkout', sprout_branch ]
	run_cmd( git_cmd )

	# sprout_build_cmd = [ APACHE_BASE_DIR + site + '/wp-content/sprout-invoices/plugin-build', 'sprout-invoices', 'dev-build', sprout_version, 'dev' ]
	# run_cmd( sprout_build_cmd )

	# mv_cmd = ['mv', path + '/build/tmp/sprout-invoices', APACHE_BASE_DIR + site + '/wp-content/plugins/']
	# response = run_cmd( mv_cmd )
	# print( response )

def main():
	try:
		os.getcwd()
	except:
		print("The Current Working Directory does not exist. Please run this script from a directory that actually exists." )
		return

	_, site, fqdn, is_site_wp, plugins, git_repos, sprout_version, sprout_branch = set_params( get_arguments() )
	mk_doc_root( site )
	create_vhost( fqdn, site )
	print( '\nenable_site: ' + enable_site( fqdn )[0][0] )
	print( '\nset_ssl: ' + set_ssl( fqdn )[0] )
	if is_site_wp:
		print('\n\nTHIS IS A WORDPRESS SITE\n\nINSTALLING WORDPRESS\n\n')
		installation_data = install_wordpress( site, fqdn )
		if plugins:
			install_plugins( plugins, site )
		clone_git_results = ''
		if sprout_version:
			install_sprout( sprout_version, sprout_branch, site )
		if git_repos:
			clone_git_results = clone_gits( git_repos, site )
		write_vhost_conf( site, installation_data, clone_git_results )
		print('\nAdmin Password: ' + installation_data['admin_pass'] + '\n')
	fix_perms( site )

main()
